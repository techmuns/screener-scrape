"""Extract the four ranking metrics from stored financial lines.

Metrics (all "higher is better"):
  * ROE %            = latest Net Profit / (Equity Capital + Reserves)
  * Sales growth %   = 3-year CAGR of the top line (Sales, or Revenue for banks)
  * Operating margin = latest OPM % (or Financing Margin % for banks)
  * Profit growth %  = 3-year CAGR of Net Profit

Line-item names differ between ordinary companies and banks/financials, so each
lookup tries a list of candidate labels.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Candidate row labels (first match wins).
TOP_LINE = ["Sales", "Revenue"]
# Only the true operating margin. Banks/financials report "Financing Margin %"
# instead, which isn't comparable (and can go negative on merger accounting), so
# we deliberately leave them without this metric — they score neutrally on it.
OP_MARGIN = ["OPM %"]

FINANCIAL_SECTORS = {"Bank", "NBFC", "Insurance"}


@dataclass
class CompanyMetrics:
    roe: float | None
    sales_growth: float | None
    operating_margin: float | None
    profit_growth: float | None


# series = {statement: {line_item: {period: value}}}
Series = dict


def _annual_series(series: Series, statement: str, candidates: list[str] | str) -> dict[date, float]:
    if isinstance(candidates, str):
        candidates = [candidates]
    stmt = series.get(statement, {})
    for name in candidates:
        if name in stmt:
            return {p: v for p, v in stmt[name].items() if v is not None}
    return {}


def _latest(series: Series, statement: str, candidates: list[str] | str) -> float | None:
    data = _annual_series(series, statement, candidates)
    if not data:
        return None
    return data[max(data)]


def _cagr(data: dict[date, float], years: int = 3) -> float | None:
    """CAGR over up to `years` intervals. Requires positive endpoints."""
    if len(data) < 2:
        return None
    periods = sorted(data)
    end_p = periods[-1]
    # Pick the point `years` back, or the earliest available if history is short.
    start_p = periods[max(0, len(periods) - 1 - years)]
    n = (end_p.year - start_p.year) or 1
    start, end = data[start_p], data[end_p]
    if start is None or end is None or start <= 0 or end <= 0:
        return None
    return ((end / start) ** (1 / n) - 1) * 100


def compute_metrics(series: Series) -> CompanyMetrics:
    net_profit = _latest(series, "pnl", "Net Profit")
    equity = _latest(series, "balance_sheet", "Equity Capital")
    reserves = _latest(series, "balance_sheet", "Reserves")

    roe = None
    if net_profit is not None and equity is not None and reserves is not None:
        book = equity + reserves
        if book > 0:
            roe = net_profit / book * 100

    sales_growth = _cagr(_annual_series(series, "pnl", TOP_LINE))
    profit_growth = _cagr(_annual_series(series, "pnl", "Net Profit"))
    operating_margin = _latest(series, "pnl", OP_MARGIN)

    return CompanyMetrics(
        roe=roe,
        sales_growth=sales_growth,
        operating_margin=operating_margin,
        profit_growth=profit_growth,
    )
