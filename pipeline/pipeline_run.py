"""Run the whole pipeline end-to-end in order.

    python -m pipeline.pipeline_run            # everything
    python -m pipeline.pipeline_run --no-fetch # skip the network ingest,
                                               # recompute from stored data

Steps: ingest (all 50) -> compute -> summarize -> export JSON -> build HTML.
"""
from __future__ import annotations

import argparse

from . import build_html, compute, export_dashboard, summarize
from .ingest import ingest_all


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run the full dashboard pipeline")
    p.add_argument("--no-fetch", action="store_true", help="skip ingest; use stored data")
    args = p.parse_args(argv)

    if not args.no_fetch:
        print("== Ingesting Nifty 50 ==")
        ingest_all()
    print("== Computing ranks / competitor / red flags ==")
    compute.run()
    print("== Generating summaries ==")
    summarize.generate_all()
    print("== Exporting dashboard JSON ==")
    export_dashboard.write_json()
    print("== Building dashboard.html ==")
    out = build_html.build()
    print(f"\nDone → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
