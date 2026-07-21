"""Ingest one company end-to-end: fetch public page -> parse -> store.

No login is required — screener company pages are public.

Usage:
    # Normal path (fetches the live public page):
    python -m pipeline.ingest --symbol RELIANCE

    # Parse a page you already saved, no network needed (handy for testing):
    python -m pipeline.ingest --symbol RELIANCE --from-file data/RELIANCE.html

Milestone 3 will add `--all` to loop the whole Nifty 50 on a daily schedule.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from sqlalchemy import delete, select

from . import nifty50
from .config import settings
from .db import create_all, session_scope
from .models import Company, FinancialLine
from .parser import ParsedCompany, parse_workbook
from .screener_client import ScreenerClient, ScreenerError
from .web_parser import parse_company_html


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


def _parse_source(symbol: str, from_file: Path | None) -> tuple[ParsedCompany, int | None, bool | None]:
    """Produce parsed line items plus (screener_id, consolidated) metadata."""
    if from_file is not None:
        if not from_file.exists():
            raise SystemExit(f"File not found: {from_file}")
        print(f"Parsing local file {from_file} (no network) ...")
        text = from_file.read_text(encoding="utf-8", errors="ignore") if from_file.suffix != ".xlsx" else None
        if from_file.suffix == ".xlsx":
            return parse_workbook(from_file), None, None
        return parse_company_html(text), ScreenerClient.extract_company_id(text), None

    client = ScreenerClient()
    print(f"Fetching public screener page for {symbol} ...")
    html, consolidated, screener_id = client.fetch_company_html(symbol)
    print(f"  fetched (screener id={screener_id}, consolidated={consolidated})")
    return parse_company_html(html), screener_id, consolidated


def ingest_symbol(symbol: str, from_file: Path | None = None) -> None:
    parsed, screener_id, consolidated = _parse_source(symbol, from_file)

    if not parsed.lines:
        raise SystemExit(
            "Parsed 0 line items — screener may have changed its page layout. "
            "Inspect the page and adjust pipeline/web_parser.py."
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


def ingest_all(delay: float | None = None) -> dict[str, str]:
    """Fetch, parse and store every Nifty 50 company. Returns per-symbol status."""
    delay = settings.request_delay if delay is None else delay
    create_all()
    results: dict[str, str] = {}
    symbols = [c.symbol for c in nifty50.NIFTY_50]
    client = ScreenerClient()

    for i, symbol in enumerate(symbols, 1):
        try:
            html, consolidated, screener_id = client.fetch_company_html(symbol)
            parsed = parse_company_html(html)
            if not parsed.lines:
                results[symbol] = "no data parsed"
                print(f"[{i:2}/{len(symbols)}] {symbol:12} ⚠ no data")
                continue
            with session_scope() as session:
                company = _upsert_company(session, symbol, screener_id, consolidated)
                count = _store_lines(session, company, parsed)
            results[symbol] = "ok"
            print(f"[{i:2}/{len(symbols)}] {symbol:12} ✓ {count} rows (consolidated={consolidated})")
        except Exception as exc:  # keep going; one bad symbol shouldn't stop the run
            results[symbol] = f"error: {exc}"
            print(f"[{i:2}/{len(symbols)}] {symbol:12} ✗ {exc}")
        if i < len(symbols):
            time.sleep(delay)

    ok = sum(1 for v in results.values() if v == "ok")
    print(f"\nDone: {ok}/{len(symbols)} companies ingested.")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest companies from screener.in")
    parser.add_argument("--symbol", help="NSE/screener symbol, e.g. RELIANCE")
    parser.add_argument("--all", action="store_true", help="Ingest the whole Nifty 50")
    parser.add_argument(
        "--from-file",
        type=Path,
        default=None,
        help="Parse a saved page (.html) or export (.xlsx) instead of the network",
    )
    args = parser.parse_args(argv)

    try:
        if args.all:
            ingest_all()
        elif args.symbol:
            ingest_symbol(args.symbol, args.from_file)
        else:
            parser.error("provide --symbol SYMBOL or --all")
    except ScreenerError as exc:
        print(f"\nScreener error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
