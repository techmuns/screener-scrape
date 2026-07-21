"""Export everything the dashboard needs into a single JSON payload.

Reads the raw + computed tables and produces one self-contained data file:
per-company metrics, ranks, red flags, summary, best competitor, and trimmed
chart series (annual revenue / net profit / margin, recent quarters).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import select

from .db import session_scope
from .metrics import TOP_LINE
from .models import Company, FinancialLine, RedFlag, Score, Summary

OUT_JSON = Path(__file__).resolve().parent.parent / "web" / "dashboard_data.json"

MAX_ANNUAL = 10
MAX_QUARTERS = 8


def _label(period: date) -> str:
    return period.strftime("%b %Y")


def _series(session, cid: int, statement: str, candidates, period_type: str) -> dict[date, float]:
    if isinstance(candidates, str):
        candidates = [candidates]
    stmt = {}
    for name in candidates:
        rows = session.execute(
            select(FinancialLine.period_end, FinancialLine.value).where(
                FinancialLine.company_id == cid,
                FinancialLine.statement == statement,
                FinancialLine.line_item == name,
            )
        ).all()
        data = {p: v for p, v in rows if v is not None}
        if data:
            return data
    return stmt


def _aligned(periods: list[date], data: dict[date, float]) -> list[float | None]:
    return [data.get(p) for p in periods]


def build_payload() -> dict:
    with session_scope() as session:
        companies = {c.id: c for c in session.scalars(select(Company)).all()}
        scores = {s.company_id: s for s in session.scalars(select(Score)).all()}
        summaries = {s.company_id: s.text for s in session.scalars(select(Summary)).all()}

        out_companies = []
        for cid, c in companies.items():
            score = scores.get(cid)
            if score is None:
                continue

            # Annual chart series (last MAX_ANNUAL years).
            revenue = _series(session, cid, "pnl", TOP_LINE, "annual")
            net_profit = _series(session, cid, "pnl", "Net Profit", "annual")
            opm = _series(session, cid, "pnl", ["OPM %", "Financing Margin %"], "annual")
            annual_periods = sorted(set(revenue) | set(net_profit))[-MAX_ANNUAL:]

            # Quarterly (last MAX_QUARTERS).
            q_rev = _series(session, cid, "quarters", ["Sales", "Revenue"], "quarter")
            q_np = _series(session, cid, "quarters", "Net Profit", "quarter")
            q_periods = sorted(set(q_rev) | set(q_np))[-MAX_QUARTERS:]

            flags = session.scalars(select(RedFlag).where(RedFlag.company_id == cid)).all()
            competitor = companies.get(score.best_competitor_id)

            out_companies.append({
                "symbol": c.symbol,
                "name": c.name,
                "sector": c.sector,
                "consolidated": c.consolidated,
                "metrics": {
                    "roe": score.roe_pct,
                    "salesGrowth": score.sales_growth_pct,
                    "operatingMargin": score.operating_margin_pct,
                    "profitGrowth": score.profit_growth_pct,
                },
                "composite": score.composite_score,
                "overallRank": score.overall_rank,
                "sectorRank": score.sector_rank,
                "bestCompetitor": (
                    {"symbol": competitor.symbol, "name": competitor.name}
                    if competitor else None
                ),
                "redFlags": [
                    {"type": f.flag_type, "severity": f.severity,
                     "value": f.value, "detail": f.detail}
                    for f in flags
                ],
                "summary": summaries.get(cid, ""),
                "annual": {
                    "labels": [_label(p) for p in annual_periods],
                    "revenue": _aligned(annual_periods, revenue),
                    "netProfit": _aligned(annual_periods, net_profit),
                    "opm": _aligned(annual_periods, opm),
                },
                "quarters": {
                    "labels": [_label(p) for p in q_periods],
                    "revenue": _aligned(q_periods, q_rev),
                    "netProfit": _aligned(q_periods, q_np),
                },
            })

        # Rank ascending; within a shared rank, higher composite shows first.
        out_companies.sort(key=lambda x: (x["overallRank"], -x["composite"]))
        sectors = sorted({c["sector"] for c in out_companies if c["sector"]})

        return {
            "universe": "Nifty 50",
            "companyCount": len(out_companies),
            "sectors": sectors,
            "metricNote": "Ranks use ROE, 3-yr sales growth, operating margin and "
                          "3-yr profit growth, each percentile-ranked across the "
                          "universe and equal-weighted. Ties share a rank.",
            "companies": out_companies,
        }


def write_json(payload: dict | None = None) -> Path:
    payload = payload or build_payload()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return OUT_JSON


if __name__ == "__main__":
    path = write_json()
    data = json.loads(path.read_text())
    print(f"Wrote {path} — {data['companyCount']} companies, {len(data['sectors'])} sectors.")
