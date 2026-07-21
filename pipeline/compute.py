"""Compute the derived layer the dashboard reads:

  * normalize the four metrics to 0-100 percentiles across the universe,
  * an equal-weighted composite score,
  * an overall rank and a within-sector rank (ties share a rank),
  * the "best competitor" = nearest neighbour in normalized-metric space,
  * red flags derived from the raw statements.

Results are written to the scores / red_flags tables.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, select

from .db import create_all, session_scope
from .metrics import FINANCIAL_SECTORS, CompanyMetrics, compute_metrics
from .models import Company, FinancialLine, RedFlag, Score

METRIC_KEYS = ["roe", "sales_growth", "operating_margin", "profit_growth"]


@dataclass
class CompanyView:
    id: int
    symbol: str
    name: str
    sector: str | None
    series: dict
    metrics: CompanyMetrics
    percentiles: dict[str, float]
    composite: float
    overall_rank: int
    sector_rank: int
    best_competitor_id: int | None


# --- data access ------------------------------------------------------------

def _load_series(session, company_id: int) -> dict:
    series: dict = defaultdict(lambda: defaultdict(dict))
    rows = session.execute(
        select(
            FinancialLine.statement,
            FinancialLine.line_item,
            FinancialLine.period_end,
            FinancialLine.value,
        ).where(FinancialLine.company_id == company_id)
    ).all()
    for statement, line_item, period_end, value in rows:
        series[statement][line_item][period_end] = value
    return series


# --- normalization ----------------------------------------------------------

def _percentile_ranks(values: dict[int, float | None]) -> dict[int, float]:
    """Map company_id -> 0..100 percentile (higher value = higher percentile).

    Missing values get a neutral 50 so one absent metric doesn't sink a company.
    """
    present = {cid: v for cid, v in values.items() if v is not None}
    out: dict[int, float] = {}
    n = len(present)
    if n <= 1:
        return {cid: 50.0 for cid in values}
    ordered = sorted(present.values())
    for cid, v in values.items():
        if v is None:
            out[cid] = 50.0
            continue
        below = sum(1 for x in ordered if x < v)
        equal = sum(1 for x in ordered if x == v)
        out[cid] = (below + 0.5 * equal) / n * 100
    return out


def _competition_rank(scores: dict[int, float]) -> dict[int, int]:
    """Standard competition ranking (1,2,2,4). Higher score = better (rank 1)."""
    ranks: dict[int, int] = {}
    for cid, sc in scores.items():
        ranks[cid] = 1 + sum(1 for other in scores.values() if other > sc)
    return ranks


def _nearest(cid: int, vectors: dict[int, list[float]]) -> int | None:
    base = vectors[cid]
    best, best_d = None, None
    for other, vec in vectors.items():
        if other == cid:
            continue
        d = sum((a - b) ** 2 for a, b in zip(base, vec))
        if best_d is None or d < best_d:
            best, best_d = other, d
    return best


# --- red flags --------------------------------------------------------------

def _quarter_series(series: dict, statement: str, item: str) -> list[tuple[date, float]]:
    data = series.get(statement, {}).get(item, {})
    return sorted((p, v) for p, v in data.items() if v is not None)


def _latest_annual(series: dict, statement: str, candidates) -> float | None:
    if isinstance(candidates, str):
        candidates = [candidates]
    stmt = series.get(statement, {})
    for name in candidates:
        data = {p: v for p, v in stmt.get(name, {}).items() if v is not None}
        if data:
            return data[max(data)]
    return None


def _sum_last(series: dict, statement: str, item: str, years: int = 3) -> float | None:
    data = sorted((p, v) for p, v in series.get(statement, {}).get(item, {}).items() if v is not None)
    if not data:
        return None
    return sum(v for _, v in data[-years:])


def compute_red_flags(series: dict, sector: str | None) -> list[dict]:
    flags: list[dict] = []
    is_financial = sector in FINANCIAL_SECTORS

    # 1) Promoter holding trend (skip if no promoter row — e.g. HDFC Bank).
    promoters = _quarter_series(series, "shareholding", "Promoters")
    if len(promoters) >= 2:
        latest = promoters[-1][1]
        prior = promoters[max(0, len(promoters) - 5)][1]  # ~4 quarters back
        delta = latest - prior
        if delta <= -3:
            sev = "red"
        elif delta <= -1:
            sev = "amber"
        else:
            sev = "green"
        flags.append({
            "flag_type": "Promoter holding trend",
            "severity": sev,
            "value": round(delta, 2),
            "detail": f"Promoters hold {latest:.1f}% ({'+' if delta >= 0 else ''}{delta:.1f} pp vs a year ago)",
        })

    # 2) Cash conversion: operating cash flow vs reported profit (non-financials).
    if not is_financial:
        cfo = _sum_last(series, "cash_flow", "Cash from Operating Activity")
        pat = _sum_last(series, "pnl", "Net Profit")
        if cfo is not None and pat is not None and pat > 0:
            ratio = cfo / pat
            if ratio < 0.4:
                sev = "red"
            elif ratio < 0.7:
                sev = "amber"
            else:
                sev = "green"
            flags.append({
                "flag_type": "Cash conversion (3y)",
                "severity": sev,
                "value": round(ratio, 2),
                "detail": f"Operating cash flow is {ratio:.0%} of net profit over 3 years",
            })

    # 3) Interest coverage (non-financials).
    if not is_financial:
        op = _latest_annual(series, "pnl", "Operating Profit")
        interest = _latest_annual(series, "pnl", "Interest")
        if op is not None and interest is not None and interest > 0:
            cover = op / interest
            if cover < 1.5:
                sev = "red"
            elif cover < 3:
                sev = "amber"
            else:
                sev = "green"
            flags.append({
                "flag_type": "Interest coverage",
                "severity": sev,
                "value": round(cover, 1),
                "detail": f"Operating profit covers interest {cover:.1f}x",
            })

    # 4) Other income share of profit. Skipped for banks/financials, where
    #    "other income" is largely core fee/treasury income, not a warning sign.
    other = _latest_annual(series, "pnl", "Other Income")
    pbt = _latest_annual(series, "pnl", "Profit before tax")
    if not is_financial and other is not None and pbt is not None and pbt > 0:
        share = other / pbt
        if share > 0.4:
            sev = "red"
        elif share > 0.25:
            sev = "amber"
        else:
            sev = "green"
        flags.append({
            "flag_type": "Other income reliance",
            "severity": sev,
            "value": round(share, 2),
            "detail": f"Other (non-core) income is {share:.0%} of pre-tax profit",
        })

    return flags


# --- orchestration ----------------------------------------------------------

def run(run_date: date | None = None) -> list[CompanyView]:
    run_date = run_date or date.today()
    create_all()

    with session_scope() as session:
        companies = session.scalars(select(Company)).all()
        views: dict[int, CompanyView] = {}
        for c in companies:
            series = _load_series(session, c.id)
            views[c.id] = CompanyView(
                id=c.id, symbol=c.symbol, name=c.name, sector=c.sector,
                series=series, metrics=compute_metrics(series),
                percentiles={}, composite=0.0, overall_rank=0, sector_rank=0,
                best_competitor_id=None,
            )

        # Percentile-normalize each metric across the whole universe.
        for key in METRIC_KEYS:
            values = {cid: getattr(v.metrics, key) for cid, v in views.items()}
            pct = _percentile_ranks(values)
            for cid, p in pct.items():
                views[cid].percentiles[key] = round(p, 1)

        # Composite = mean of the four percentiles; round for shared ranks.
        composites: dict[int, float] = {}
        for cid, v in views.items():
            v.composite = round(sum(v.percentiles[k] for k in METRIC_KEYS) / len(METRIC_KEYS), 1)
            composites[cid] = round(v.composite)

        # Overall + within-sector ranks (ties share a rank).
        overall = _competition_rank(composites)
        by_sector: dict[str, dict[int, float]] = defaultdict(dict)
        for cid, v in views.items():
            by_sector[v.sector or "Other"][cid] = composites[cid]
        sector_ranks: dict[int, int] = {}
        for group in by_sector.values():
            sector_ranks.update(_competition_rank(group))
        for cid, v in views.items():
            v.overall_rank = overall[cid]
            v.sector_rank = sector_ranks[cid]

        # Best competitor: nearest neighbour in percentile space.
        vectors = {cid: [v.percentiles[k] for k in METRIC_KEYS] for cid, v in views.items()}
        for cid, v in views.items():
            v.best_competitor_id = _nearest(cid, vectors)

        # Persist scores + red flags.
        session.execute(delete(Score))
        session.execute(delete(RedFlag))
        for v in views.values():
            session.add(Score(
                company_id=v.id, run_date=run_date,
                roe_pct=v.metrics.roe,
                sales_growth_pct=v.metrics.sales_growth,
                operating_margin_pct=v.metrics.operating_margin,
                profit_growth_pct=v.metrics.profit_growth,
                composite_score=v.composite,
                overall_rank=v.overall_rank,
                sector_rank=v.sector_rank,
                best_competitor_id=v.best_competitor_id,
            ))
            for f in compute_red_flags(v.series, v.sector):
                session.add(RedFlag(
                    company_id=v.id, run_date=run_date,
                    flag_type=f["flag_type"], severity=f["severity"],
                    value=f["value"], detail=f["detail"],
                ))

        return sorted(views.values(), key=lambda x: x.overall_rank)


if __name__ == "__main__":
    ranked = run()
    print(f"Computed {len(ranked)} companies. Top 10 by composite:\n")
    print(f"{'#':>3}  {'Symbol':12} {'Sector':14} {'Score':>6}  {'ROE%':>6} {'SalesG%':>7} {'OPM%':>6} {'PatG%':>6}")
    for v in ranked[:10]:
        m = v.metrics
        def f(x): return f"{x:6.1f}" if x is not None else "   n/a"
        print(f"{v.overall_rank:>3}  {v.symbol:12} {(v.sector or ''):14} {v.composite:6.1f}  "
              f"{f(m.roe)} {f(m.sales_growth):>7} {f(m.operating_margin)} {f(m.profit_growth)}")
