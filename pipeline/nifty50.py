"""Nifty 50 constituents mapped to their screener.in symbols and sectors.

`symbol` is the screener/NSE ticker used in the URL:
    https://www.screener.in/company/<symbol>/

Sector is our own coarse grouping, used for the within-sector rank. It is kept
deliberately simple (a handful of buckets) rather than mirroring NSE's granular
industry taxonomy, so each bucket has enough members to rank within.

NOTE: Nifty 50 membership changes over time (NSE reviews it twice a year). This
snapshot is current as of 2026-07. Treat it as data to update, not gospel.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Constituent:
    symbol: str
    name: str
    sector: str


NIFTY_50: list[Constituent] = [
    Constituent("RELIANCE", "Reliance Industries", "Energy"),
    Constituent("ONGC", "Oil & Natural Gas Corporation", "Energy"),
    Constituent("BPCL", "Bharat Petroleum", "Energy"),
    Constituent("COALINDIA", "Coal India", "Energy"),
    Constituent("NTPC", "NTPC", "Power"),
    Constituent("POWERGRID", "Power Grid Corporation", "Power"),
    Constituent("TATAPOWER", "Tata Power", "Power"),
    Constituent("ADANIENT", "Adani Enterprises", "Diversified"),
    Constituent("ADANIPORTS", "Adani Ports & SEZ", "Infrastructure"),
    Constituent("LT", "Larsen & Toubro", "Infrastructure"),
    Constituent("ULTRACEMCO", "UltraTech Cement", "Materials"),
    Constituent("GRASIM", "Grasim Industries", "Materials"),
    Constituent("JSWSTEEL", "JSW Steel", "Materials"),
    Constituent("TATASTEEL", "Tata Steel", "Materials"),
    Constituent("HINDALCO", "Hindalco Industries", "Materials"),
    Constituent("TCS", "Tata Consultancy Services", "IT"),
    Constituent("INFY", "Infosys", "IT"),
    Constituent("WIPRO", "Wipro", "IT"),
    Constituent("HCLTECH", "HCL Technologies", "IT"),
    Constituent("TECHM", "Tech Mahindra", "IT"),
    Constituent("HDFCBANK", "HDFC Bank", "Bank"),
    Constituent("ICICIBANK", "ICICI Bank", "Bank"),
    Constituent("SBIN", "State Bank of India", "Bank"),
    Constituent("KOTAKBANK", "Kotak Mahindra Bank", "Bank"),
    Constituent("AXISBANK", "Axis Bank", "Bank"),
    Constituent("INDUSINDBK", "IndusInd Bank", "Bank"),
    Constituent("BAJFINANCE", "Bajaj Finance", "NBFC"),
    Constituent("BAJAJFINSV", "Bajaj Finserv", "NBFC"),
    Constituent("SBILIFE", "SBI Life Insurance", "Insurance"),
    Constituent("HDFCLIFE", "HDFC Life Insurance", "Insurance"),
    Constituent("HINDUNILVR", "Hindustan Unilever", "FMCG"),
    Constituent("ITC", "ITC", "FMCG"),
    Constituent("NESTLEIND", "Nestle India", "FMCG"),
    Constituent("BRITANNIA", "Britannia Industries", "FMCG"),
    Constituent("TATACONSUM", "Tata Consumer Products", "FMCG"),
    Constituent("SUNPHARMA", "Sun Pharmaceutical", "Pharma"),
    Constituent("CIPLA", "Cipla", "Pharma"),
    Constituent("DRREDDY", "Dr. Reddy's Laboratories", "Pharma"),
    Constituent("DIVISLAB", "Divi's Laboratories", "Pharma"),
    Constituent("APOLLOHOSP", "Apollo Hospitals", "Healthcare"),
    Constituent("MARUTI", "Maruti Suzuki India", "Auto"),
    Constituent("TATAMOTORS", "Tata Motors", "Auto"),
    Constituent("M&M", "Mahindra & Mahindra", "Auto"),
    Constituent("BAJAJ-AUTO", "Bajaj Auto", "Auto"),
    Constituent("EICHERMOT", "Eicher Motors", "Auto"),
    Constituent("HEROMOTOCO", "Hero MotoCorp", "Auto"),
    Constituent("ASIANPAINT", "Asian Paints", "Consumer Durables"),
    Constituent("TITAN", "Titan Company", "Consumer Durables"),
    Constituent("BHARTIARTL", "Bharti Airtel", "Telecom"),
    Constituent("TRENT", "Trent", "Retail"),
]


BY_SYMBOL: dict[str, Constituent] = {c.symbol: c for c in NIFTY_50}


def get(symbol: str) -> Constituent | None:
    return BY_SYMBOL.get(symbol.upper())
