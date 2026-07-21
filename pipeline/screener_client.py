"""Fetch a screener.in company page.

Screener company pages are PUBLIC — the financial tables (quarters, P&L, balance
sheet, cash flow, ratios, shareholding) render without any login. So this client
needs no cookie or password: it just downloads the page HTML. (The login-only
"Export to Excel" button is no longer used.)

We prefer the consolidated view when a company reports one, falling back to
standalone otherwise.
"""
from __future__ import annotations

import re

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import settings

BASE = "https://www.screener.in"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Screener embeds its numeric company id in on-page data-urls, e.g.
# data-url="/results/rpt/2726/" or "/trades/company-2726/".
_ID_PATTERNS = [
    re.compile(r"/results/rpt/(\d+)/"),
    re.compile(r"/company/(\d+)/"),
    re.compile(r"company-(\d+)"),
    re.compile(r'data-company-id="(\d+)"'),
]


class ScreenerError(Exception):
    """Base class for client errors."""


class ScreenerNotFound(ScreenerError):
    """The company symbol does not resolve to a screener page."""


class ScreenerClient:
    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=16),
        reraise=True,
    )
    def _get(self, url: str) -> requests.Response:
        return self._session.get(url, timeout=30, allow_redirects=True)

    def fetch_company_html(self, symbol: str) -> tuple[str, bool, int | None]:
        """Return (html, consolidated_flag, screener_company_id).

        Tries the consolidated view first when preferred, falling back to the
        standalone page for companies that don't report consolidated figures.
        """
        symbol = symbol.upper()
        attempts: list[str] = []
        if settings.prefer_consolidated:
            attempts.append(f"{BASE}/company/{symbol}/consolidated/")
        attempts.append(f"{BASE}/company/{symbol}/")

        last_status = None
        for url in attempts:
            resp = self._get(url)
            last_status = resp.status_code
            if resp.status_code == 404:
                continue
            if resp.ok and 'id="profit-loss"' in resp.text:
                consolidated = "Consolidated Figures" in resp.text
                return resp.text, consolidated, self.extract_company_id(resp.text)

        raise ScreenerNotFound(
            f"No usable screener page for symbol '{symbol}' (last HTTP {last_status}). "
            "Check the symbol spelling on screener.in."
        )

    @staticmethod
    def extract_company_id(html: str) -> int | None:
        for pattern in _ID_PATTERNS:
            match = pattern.search(html)
            if match:
                return int(match.group(1))
        return None
