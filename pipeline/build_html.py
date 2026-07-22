"""Inject the exported JSON into the dashboard template -> a standalone file.

Produces web/dashboard.html: the template with the data embedded, so it opens
in a browser (or as an Artifact) with no server and no external requests.
"""
from __future__ import annotations

import json
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
TEMPLATE = WEB / "template.html"
DATA = WEB / "dashboard_data.json"
# index.html is what a static host (Cloudflare Pages) serves at the site root,
# and it is fully self-contained (data embedded), so no build step is needed on
# the host. dashboard.html is kept as an identical copy for the published link.
OUT = WEB / "index.html"
ALIAS = WEB / "dashboard.html"
PLACEHOLDER = "__DASHBOARD_DATA__"


def build() -> Path:
    template = TEMPLATE.read_text(encoding="utf-8")
    data = json.loads(DATA.read_text(encoding="utf-8"))
    # Compact JSON; neutralise any "</script>" sequences just in case.
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = template.replace(PLACEHOLDER, blob)
    OUT.write_text(html, encoding="utf-8")
    ALIAS.write_text(html, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    path = build()
    kb = path.stat().st_size / 1024
    print(f"Wrote {path} ({kb:.0f} KB)")
