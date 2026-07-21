"""Authenticated screener.in client.

The account uses Google sign-in, so we authenticate with the browser
`sessionid` cookie (see .env.example) rather than a username/password.

Responsibilities:
  * hold the session cookie,
  * fetch a company page and discover its numeric screener id,
  * download the "Export to Excel" workbook,
  * raise a clear, actionable error when the cookie has expired.
"""
from __future__ import annotations

import re
from pathlib import Path

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import DATA_DIR, settings

BASE = "https://www.screener.in"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Screener embeds the numeric company id in a few places; try each in order.
_ID_PATTERNS = [
    re.compile(r"/user/company/export/(\d+)/"),
    re.compile(r'data-company-id="(\d+)"'),
    re.compile(r'"company_id"\s*:\s*(\d+)'),
    re.compile(r"Company\.init\((\d+)"),
]


class ScreenerError(Exception):
    """Base class for client errors."""


class ScreenerAuthError(ScreenerError):
    """The session cookie is missing or expired — user must refresh it."""


class ScreenerNotFound(ScreenerError):
    """The company symbol does not resolve to a screener page."""


def _looks_like_login_page(text: str) -> bool:
    lowered = text.lower()
    return "sign in" in lowered and "id_username" in lowered


class ScreenerClient:
    def __init__(self, session_cookie: str | None = None) -> None:
        cookie = session_cookie if session_cookie is not None else settings.screener_session_cookie
        if not cookie:
            raise ScreenerAuthError(
                "No SCREENER_SESSION_COOKIE set. Log in to screener.in in your "
                "browser, copy the 'sessionid' cookie into your .env file, and "
                "re-run. See .env.example for step-by-step instructions."
            )
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})
        self._session.cookies.set("sessionid", cookie, domain="www.screener.in")
        if settings.screener_csrf_token:
            self._session.cookies.set(
                "csrftoken", settings.screener_csrf_token, domain="www.screener.in"
            )

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=16),
        reraise=True,
    )
    def _get(self, url: str, **kwargs) -> requests.Response:
        resp = self._session.get(url, timeout=30, allow_redirects=True, **kwargs)
        # An expired cookie yields a redirect to /login/ or the login HTML.
        if resp.status_code in (401, 403):
            raise ScreenerAuthError(
                "Screener rejected the request (HTTP %s). Your session cookie has "
                "likely expired — refresh SCREENER_SESSION_COOKIE in .env." % resp.status_code
            )
        return resp

    def fetch_company_page(self, symbol: str) -> tuple[str, bool]:
        """Return (html, consolidated_flag).

        Tries the consolidated view first when preferred, falling back to the
        standalone page for companies that don't report consolidated figures.
        """
        symbol = symbol.upper()
        attempts: list[tuple[str, bool]] = []
        if settings.prefer_consolidated:
            attempts.append((f"{BASE}/company/{symbol}/consolidated/", True))
        attempts.append((f"{BASE}/company/{symbol}/", False))

        last_status = None
        for url, consolidated in attempts:
            resp = self._get(url)
            last_status = resp.status_code
            if resp.status_code == 404:
                continue
            if _looks_like_login_page(resp.text):
                raise ScreenerAuthError(
                    "Got the login page instead of company data — the session "
                    "cookie has expired. Refresh SCREENER_SESSION_COOKIE in .env."
                )
            if resp.ok:
                return resp.text, consolidated

        raise ScreenerNotFound(
            f"No screener page for symbol '{symbol}' (last HTTP {last_status})."
        )

    @staticmethod
    def extract_company_id(html: str) -> int:
        for pattern in _ID_PATTERNS:
            match = pattern.search(html)
            if match:
                return int(match.group(1))
        raise ScreenerError(
            "Could not find the screener company id in the page HTML. Screener "
            "may have changed its markup — the id-discovery patterns need updating."
        )

    def download_export(self, company_id: int, dest: Path | None = None) -> Path:
        """Download the Excel export for a company id and return the file path."""
        url = f"{BASE}/user/company/export/{company_id}/"
        resp = self._get(url)
        content_type = resp.headers.get("Content-Type", "")
        # A logged-out session returns HTML (the login page) with 200.
        if "spreadsheet" not in content_type and "excel" not in content_type:
            if _looks_like_login_page(resp.text):
                raise ScreenerAuthError(
                    "Export returned the login page — session cookie expired. "
                    "Refresh SCREENER_SESSION_COOKIE in .env."
                )
            raise ScreenerError(
                f"Unexpected export content-type '{content_type}' for company "
                f"{company_id}; expected an .xlsx."
            )

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        dest = dest or DATA_DIR / f"{company_id}.xlsx"
        dest.write_bytes(resp.content)
        return dest

    def export_for_symbol(self, symbol: str) -> tuple[Path, int, bool]:
        """Full path: symbol -> (xlsx path, company_id, consolidated_flag)."""
        html, consolidated = self.fetch_company_page(symbol)
        company_id = self.extract_company_id(html)
        dest = DATA_DIR / f"{symbol.upper()}.xlsx"
        self.download_export(company_id, dest)
        return dest, company_id, consolidated
