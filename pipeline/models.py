"""Database schema.

Design note — why a long/EAV-style raw store instead of one column per metric:
Screener's export rows are NOT identical across companies. A bank's P&L has
"Financing Profit"/"Financing Margin" rows; a manufacturer has "Operating
Profit"/"OPM". Mapping every possible row to a fixed column would be brittle and
lossy. So the raw layer stores each cell as (statement, period, line_item ->
value). The compute layer (Milestone 4) reads the specific line items it needs
and writes the tidy, fixed-shape `scores` / `red_flags` / `summaries` tables the
dashboard consumes.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Screener/NSE symbol, e.g. "RELIANCE". Our stable natural key.
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Screener's internal numeric company id, discovered from the page.
    screener_company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Whether the stored figures are consolidated (True) or standalone (False).
    consolidated: Mapped[bool | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    lines: Mapped[list["FinancialLine"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class FinancialLine(Base):
    """One cell of the export: a single line item for a single period."""

    __tablename__ = "financial_lines"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "statement",
            "period_type",
            "period_end",
            "line_item",
            name="uq_financial_line",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    # "pnl" | "quarters" | "balance_sheet" | "cash_flow"
    statement: Mapped[str] = mapped_column(String(32), index=True)
    # "annual" | "quarter"
    period_type: Mapped[str] = mapped_column(String(16))
    # Last day of the reporting period (e.g. 2024-03-31).
    period_end: Mapped[date] = mapped_column(Date)
    # Row label exactly as screener names it, e.g. "Operating Profit".
    line_item: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)

    company: Mapped[Company] = relationship(back_populates="lines")


# --- Computed tables (populated from Milestone 4 onward) --------------------
# Defined now so the schema is complete; ingestion (M2) does not touch them.


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint("company_id", "run_date", name="uq_score_run"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    run_date: Mapped[date] = mapped_column(Date, index=True)

    roe_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    sales_growth_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_margin_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_growth_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    composite_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sector_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_competitor_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True
    )


class RedFlag(Base):
    __tablename__ = "red_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    run_date: Mapped[date] = mapped_column(Date, index=True)
    flag_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))  # green | amber | red
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail: Mapped[str | None] = mapped_column(String(512), nullable=True)


class Summary(Base):
    __tablename__ = "summaries"
    __table_args__ = (
        UniqueConstraint("company_id", "run_date", name="uq_summary_run"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    run_date: Mapped[date] = mapped_column(Date, index=True)
    text: Mapped[str] = mapped_column(String(2048))
