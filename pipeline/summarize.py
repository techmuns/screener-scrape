"""Generate the 4-5 line plain-English summary for each company.

This is a deterministic, template-based writer built from the computed numbers —
descriptive, never advisory (keeps us clear of investment-advice territory).
It can be upgraded to a Claude-API writer later (Milestone 5+) without changing
anything downstream: the dashboard just reads the `summaries` table.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select

from .db import create_all, session_scope
from .models import Company, RedFlag, Score, Summary


def _pct(x: float | None, digits: int = 0) -> str:
    return f"{x:.{digits}f}%" if x is not None else "n/a"


def _growth_word(g: float | None) -> str:
    if g is None:
        return "unclear"
    if g >= 15:
        return "rapidly"
    if g >= 8:
        return "steadily"
    if g >= 0:
        return "slowly"
    return "in decline,"


def _roe_word(r: float | None) -> str:
    if r is None:
        return "unclear"
    if r >= 20:
        return "strong"
    if r >= 15:
        return "healthy"
    if r >= 10:
        return "moderate"
    return "modest"


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1:'st',2:'nd',3:'rd'}.get(n % 10,'th')}"


def _possessive(name: str) -> str:
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def build_summary(name: str, sector: str | None, score: Score, flags: list[RedFlag],
                  competitor: str | None) -> str:
    m_roe, m_sg = score.roe_pct, score.sales_growth_pct
    m_opm, m_pg = score.operating_margin_pct, score.profit_growth_pct

    lines: list[str] = []

    # 1) Growth.
    if m_sg is not None or m_pg is not None:
        lines.append(
            f"Over the last three years {_possessive(name)} revenue grew {_growth_word(m_sg)} "
            f"(~{_pct(m_sg)} a year) and net profit {_growth_word(m_pg)} (~{_pct(m_pg)} a year)."
        )

    # 2) Profitability.
    prof_bits = []
    if m_roe is not None:
        prof_bits.append(f"a {_pct(m_roe)} return on equity")
    if m_opm is not None:
        prof_bits.append(f"a {_pct(m_opm)} operating margin")
    if prof_bits:
        lines.append(
            f"Profitability looks {_roe_word(m_roe)} — {' and '.join(prof_bits)}."
        )

    # 3) Ranking.
    lines.append(
        f"On these fundamentals it ranks {_ordinal(score.overall_rank)} of 50 overall, "
        f"and {_ordinal(score.sector_rank)} among its {sector or 'sector'} peers."
    )

    # 4) Red flags.
    concerns = [f for f in flags if f.severity in ("amber", "red")]
    if not concerns:
        lines.append("No major accounting red flags stand out in the reported data.")
    else:
        worst = ", ".join(f"{f.flag_type.lower()}" for f in concerns[:3])
        lines.append(f"Worth a closer look: {worst}.")

    # 5) Closest peer.
    if competitor:
        lines.append(f"Its closest financial look-alike in the Nifty 50 is {competitor}.")

    return " ".join(lines)


def generate_all(run_date: date | None = None) -> int:
    run_date = run_date or date.today()
    create_all()
    with session_scope() as session:
        companies = {c.id: c for c in session.scalars(select(Company)).all()}
        scores = {s.company_id: s for s in session.scalars(select(Score)).all()}

        session.execute(delete(Summary))
        count = 0
        for cid, company in companies.items():
            score = scores.get(cid)
            if score is None:
                continue
            flags = session.scalars(select(RedFlag).where(RedFlag.company_id == cid)).all()
            competitor = companies.get(score.best_competitor_id)
            text = build_summary(
                company.name, company.sector, score, list(flags),
                competitor.name if competitor else None,
            )
            session.add(Summary(company_id=cid, run_date=run_date, text=text))
            count += 1
        return count


if __name__ == "__main__":
    n = generate_all()
    print(f"Generated {n} summaries. Example:\n")
    with session_scope() as s:
        from .models import Summary as S
        row = s.scalars(select(S)).first()
        c = s.get(Company, row.company_id)
        print(f"[{c.symbol}] {row.text}")
