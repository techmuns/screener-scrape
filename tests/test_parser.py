"""Parser tests against a synthetic screener-shaped workbook.

We build a workbook that mimics the "Data Sheet" layout (stacked sections with a
period-header row) so we can verify parsing logic without a live screener login.
Replace/extend the fixture once a real export is available.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from openpyxl import Workbook

from pipeline.parser import parse_workbook


def _build_fixture(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Data Sheet"

    rows = [
        ["PROFIT & LOSS"],
        ["Report Date", "Mar-2022", "Mar-2023", "Mar-2024"],
        ["Sales", 100, 120, 150],
        ["Operating Profit", 20, 26, 33],
        ["OPM %", "20%", "21.6%", "22%"],
        ["Net profit", 12, 15, 20],
        [],
        ["QUARTERS"],
        ["Report Date", "Dec-2023", "Mar-2024", "Jun-2024"],
        ["Sales", 38, 40, 42],
        ["Net profit", 5, 6, 5.5],
        [],
        ["BALANCE SHEET"],
        ["Report Date", "Mar-2022", "Mar-2023", "Mar-2024"],
        ["Equity Share Capital", 10, 10, 10],
        ["Reserves", 80, 92, 108],
        ["Total", 200, 230, 260],          # liabilities total
        ["Net Block", 90, 100, 110],
        ["Total", 200, 230, 260],          # assets total -> duplicate label
        [],
        ["CASH FLOW:"],
        ["Report Date", "Mar-2022", "Mar-2023", "Mar-2024"],
        ["Cash from Operating Activity", 18, 22, 25],
        ["Net Cash Flow", 2, -1, 4],
        [],
        ["DERIVED:"],
        ["Report Date", "Mar-2022", "Mar-2023", "Mar-2024"],
        ["Return on Equity", "13%", "15%", "17%"],  # should be ignored
    ]
    for r in rows:
        ws.append(r)
    wb.save(path)


def test_parse_workbook(tmp_path: Path) -> None:
    fixture = tmp_path / "sample.xlsx"
    _build_fixture(fixture)

    parsed = parse_workbook(fixture)
    lines = {(l.statement, l.line_item, l.period_end): l.value for l in parsed.lines}

    # P&L values and percentage coercion.
    assert lines[("pnl", "Sales", date(2024, 3, 31))] == 150
    assert lines[("pnl", "OPM %", date(2023, 3, 31))] == 21.6
    assert lines[("pnl", "Net profit", date(2022, 3, 31))] == 12

    # Quarters section parsed with its own periods.
    assert lines[("quarters", "Sales", date(2024, 6, 30))] == 42

    # Duplicate "Total" in the balance sheet is disambiguated, not dropped.
    assert lines[("balance_sheet", "Total", date(2024, 3, 31))] == 260
    assert lines[("balance_sheet", "Total (2)", date(2024, 3, 31))] == 260

    # Cash flow, including a negative value.
    assert lines[("cash_flow", "Net Cash Flow", date(2023, 3, 31))] == -1

    # DERIVED section is ignored.
    assert not any(l.statement == "derived" for l in parsed.lines)
    assert not any(l.line_item == "Return on Equity" for l in parsed.lines)


def test_period_count(tmp_path: Path) -> None:
    fixture = tmp_path / "sample.xlsx"
    _build_fixture(fixture)
    parsed = parse_workbook(fixture)

    pnl_periods = {l.period_end for l in parsed.by_statement("pnl")}
    assert pnl_periods == {date(2022, 3, 31), date(2023, 3, 31), date(2024, 3, 31)}
