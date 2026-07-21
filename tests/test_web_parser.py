"""Tests for the public-page HTML parser against a synthetic screener layout.

Covers both header styles screener uses: `data-date-key` columns (statements)
and plain-text "Sep 2023" columns (shareholding).
"""
from __future__ import annotations

from datetime import date

from pipeline.web_parser import parse_company_html

SAMPLE_HTML = """
<html><body>
  <section id="profit-loss" class="card">
    <h2>Profit &amp; Loss</h2>
    <table class="data-table">
      <thead><tr>
        <th class="text"></th>
        <th data-date-key="2023-03-31">Mar 2023</th>
        <th data-date-key="2024-03-31">Mar 2024</th>
      </tr></thead>
      <tbody>
        <tr><td class="text"><button>Sales<span>+</span></button></td>
            <td>1,00,000</td><td>1,20,000</td></tr>
        <tr><td class="text">Operating Profit</td>
            <td>20,000</td><td>26,000</td></tr>
        <tr><td class="text">Net Profit</td>
            <td>12,000</td><td>-1,500</td></tr>
      </tbody>
    </table>
  </section>

  <section id="shareholding" class="card">
    <h2>Shareholding Pattern</h2>
    <div id="quarterly-shp">
      <table class="data-table">
        <thead><tr>
          <th class="text"></th>
          <th>Dec 2023</th>
          <th>Mar 2024</th>
        </tr></thead>
        <tbody>
          <tr><td class="text">Promoters</td><td>50.30%</td><td>50.48%</td></tr>
          <tr><td class="text">FIIs</td><td>22.10%</td><td>22.60%</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</body></html>
"""


def test_data_key_headers_and_values():
    parsed = parse_company_html(SAMPLE_HTML)
    lines = {(l.statement, l.line_item, l.period_end): l.value for l in parsed.lines}

    # Indian-format commas ("1,00,000") coerce correctly.
    assert lines[("pnl", "Sales", date(2024, 3, 31))] == 120000
    # Negative values survive.
    assert lines[("pnl", "Net Profit", date(2024, 3, 31))] == -1500
    # The "+" expand marker is stripped from the label.
    assert ("pnl", "Sales", date(2023, 3, 31)) in lines


def test_text_headers_for_shareholding():
    parsed = parse_company_html(SAMPLE_HTML)
    share = {(l.line_item, l.period_end): l.value for l in parsed.lines if l.statement == "shareholding"}
    # "Mar 2024" text header parsed to the month-end date.
    assert share[("Promoters", date(2024, 3, 31))] == 50.48
    assert share[("FIIs", date(2023, 12, 31))] == 22.10
