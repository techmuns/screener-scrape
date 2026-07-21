"""Ingest one company end-to-end: download -> parse -> store.

Usage:
    # Full path (needs SCREENER_SESSION_COOKIE in .env):
    python -m pipeline.ingest --symbol RELIANCE

    # Parse a workbook you already downloaded (no network / no cookie needed) —
    # handy for testing the parser against a real export:
    python -m pipeline.ingest --symbol RELIANCE --from-file data/RELIANCE.xlsx

Milestone 3 will add `--all` to loop the whole Nifty 50 on a daily schedule.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import delete, select

from . import nifty50
from .db import create_all, session_scope
from .models import Company, FinancialLine
from .parser import ParsedCompany, parse_workbook
from .screener_client import ScreenerClient, ScreenerError


def _upsert_company(session, symbol: str, screener_id: int | None, consolidated: bool | None) -> Company:
    symbol = symbol.upper()
    company = session.scalar(select(Company).where(Company.symbol == symbol))
    constituent = nifty50.get(symbol)
    if company is None:
        company = Company(symbol=symbol)
        session.add(company)
    company.name = constituent.name if constituent else symbol
    company.sector = constituent.sector if constituent else None
    if screener_id is not None:
        company.screener_company_id = screener_id
    if consolidated is not None:
        company.consolidated = consolidated
    session.flush()  # assign company.id
    return company


def _store_lines(session, company: Company, parsed: ParsedCompany) -> int:
    # Replace-all: simplest correct semantics for a periodic refresh.
    session.execute(delete(FinancialLine).where(FinancialLine.company_id == company.id))
    for rec in parsed.lines:
        session.add(
            FinancialLine(
                company_id=company.id,
                statement=rec.statement,
                period_type=rec.period_type,
                period_end=rec.period_end,
                line_item=rec.line_item,
                value=rec.value,
            )
        )
    return len(parsed.lines)


def ingest_symbol(symbol: str, from_file: Path | None = None) -> None:
    screener_id: int | None = None
    consolidated: bool | None = None

    if from_file is not None:
        xlsx_path = from_file
        if not xlsx_path.exists():
            raise SystemExit(f"File not found: {xlsx_path}")
        print(f"Parsing local file {xlsx_path} (no network) ...")
    else:
        client = ScreenerClient()
        print(f"Downloading export for {symbol} from screener.in ...")
        xlsx_path, screener_id, consolidated = client.export_for_symbol(symbol)
        print(f"  saved {xlsx_path} (screener id={screener_id}, consolidated={consolidated})")

    parsed = parse_workbook(xlsx_path)
    if not parsed.lines:
        raise SystemExit(
            "Parsed 0 line items — the export layout may differ from what the "
            "parser expects. Inspect the file and adjust pipeline/parser.py."
        )

    create_all()
    with session_scope() as session:
        company = _upsert_company(session, symbol, screener_id, consolidated)
        count = _store_lines(session, company, parsed)

    statements = sorted({r.statement for r in parsed.lines})
    periods = sorted({r.period_end for r in parsed.lines})
    print(
        f"Stored {count} line items for {symbol}: "
        f"statements={statements}, periods {periods[0]}..{periods[-1]}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest one company from screener.in")
    parser.add_argument("--symbol", required=True, help="NSE/screener symbol, e.g. RELIANCE")
    parser.add_argument(
        "--from-file",
        type=Path,
        default=None,
        help="Parse a pre-downloaded .xlsx instead of hitting the network",
    )
    args = parser.parse_args(argv)

    try:
        ingest_symbol(args.symbol, args.from_file)
    except ScreenerError as exc:
        print(f"\nScreener error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
