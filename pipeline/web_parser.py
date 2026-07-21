"""Parse a screener.in company page (public HTML, no login required).

Screener renders each statement as a <section id="..."> containing a
<table class="data-table">. Column headers carry an exact ISO date in a
`data-date-key` attribute (e.g. 2024-03-31), and each body row is a label cell
followed by value cells. We turn that into the same LineRecord shape the rest of
the pipeline already uses, so nothing downstream changes.
"""
from __future__ import annotations

from datetime import date

from bs4 import BeautifulSoup

from .parser import LineRecord, ParsedCompany  # reuse the shared data classes
from .parser import _parse_period as _parse_text_period  # "Sep 2023" fallback

# Screener section id -> (statement key, period_type)
_SECTIONS: dict[str, tuple[str, str]] = {
    "quarters": ("quarters", "quarter"),
    "profit-loss": ("pnl", "annual"),
    "balance-sheet": ("balance_sheet", "annual"),
    "cash-flow": ("cash_flow", "annual"),
    "ratios": ("ratios", "annual"),
    "shareholding": ("shareholding", "quarter"),
}


def _parse_date_key(value: str | None) -> date | None:
    if not value:
        return None
    try:
        y, m, d = (int(x) for x in value.split("-"))
        return date(y, m, d)
    except (ValueError, AttributeError):
        return None


def _parse_value(text: str) -> float | None:
    cleaned = (
        text.strip()
        .replace(",", "")
        .replace("%", "")
        .replace("₹", "")
        .replace("\xa0", "")
    )
    if cleaned in {"", "-", "NA", "N/A"}:
        return None
    # Screener shows negatives with a leading minus; guard against stray chars.
    try:
        return float(cleaned)
    except ValueError:
        return None


def _clean_label(text: str) -> str:
    # Row labels may include a trailing "+" (expandable) and stray whitespace.
    return " ".join(text.replace("+", " ").split()).strip()


def parse_company_html(html: str) -> ParsedCompany:
    soup = BeautifulSoup(html, "lxml")
    parsed = ParsedCompany()

    for section_id, (statement, period_type) in _SECTIONS.items():
        section = soup.find("section", id=section_id)
        if section is None:
            continue
        table = section.find("table", class_="data-table")
        if table is None:
            continue

        # Column periods, in order, from the header row's date keys.
        # Most tables tag columns with an ISO `data-date-key`; the shareholding
        # table instead uses plain text like "Sep 2023", so fall back to that.
        header_cells = table.select("thead th")
        periods: list[date | None] = []
        for th in header_cells:
            period = _parse_date_key(th.get("data-date-key"))
            if period is None:
                period = _parse_text_period(th.get_text())
            periods.append(period)

        for tr in table.select("tbody tr"):
            cells = tr.find_all("td")
            if not cells:
                continue
            label = _clean_label(cells[0].get_text())
            if not label:
                continue
            for col_idx, td in enumerate(cells):
                if col_idx == 0 or col_idx >= len(periods):
                    continue
                period = periods[col_idx]
                if period is None:
                    continue
                value = _parse_value(td.get_text())
                parsed.lines.append(
                    LineRecord(statement, period_type, period, label, value)
                )

    return parsed
