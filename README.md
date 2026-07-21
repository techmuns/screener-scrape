# screener-scrape

A custom web dashboard for fundamental analysis of Indian stocks, sourced from
[screener.in](https://www.screener.in). Pick a company and get its financials,
a 3‑year plain‑English summary, a normalized rank vs. peers, its closest
financial competitor, and an accounting red‑flag panel.

Scope for v1: the **Nifty 50**.

> **Disclaimer:** This is an educational tool. Nothing here is investment advice.

## Architecture

Data ingestion is a **pipeline**, deliberately decoupled from the dashboard —
the app never scrapes screener on click; it reads from our own database.

```
 daily job ─► screener.in "Export to Excel" (×50)
                    │
                    ▼
          parse .xlsx  ─►  Postgres  ◄─  compute: normalize · ranks ·
                    │                     similarity · red-flags · summary
                    ▼
                 FastAPI  ─►  React dashboard
```

| Layer      | Tech                         | Status |
|------------|------------------------------|--------|
| Pipeline   | Python (requests, openpyxl, SQLAlchemy) | ✅ Milestones 1–2 |
| Database   | Postgres                     | ✅ schema defined |
| Compute    | ranks · similarity · flags   | ⬜ Milestone 4 |
| Summary    | Claude API                   | ⬜ Milestone 5 |
| API        | FastAPI                      | ⬜ Milestone 6 |
| Frontend   | React (Vite)                 | ⬜ Milestone 7 |

### Ranking (Milestone 4, agreed design)
Composite of **ROE, sales growth, operating margin, profit growth**, each
normalized to a percentile across the universe and equal‑weighted. We publish
**two ranks** — an overall rank and a within‑sector rank (banks/IT/FMCG etc.
aren't directly comparable). Ties share a rank. "Best competitor" is the
nearest neighbour in that same normalized metric space.

## Getting started

### 1. Configure secrets
```bash
cp .env.example .env
```
This screener account uses **Google sign‑in**, so there's no password to
automate. Instead paste the browser session cookie into `.env`:

1. Log in to screener.in in your browser.
2. DevTools → Application → Cookies → `https://www.screener.in`.
3. Copy the **`sessionid`** value into `SCREENER_SESSION_COOKIE` in `.env`.

The cookie lasts a few weeks. When it expires the pipeline prints a clear
"cookie expired — refresh it" message. `.env` is gitignored and never committed.

### 2. Start Postgres
```bash
docker compose up -d db
```

### 3. Install deps
```bash
pip install -r requirements.txt
```

### 4. Ingest a company
```bash
# Full path (needs the session cookie):
python -m pipeline.ingest --symbol RELIANCE

# Or parse an already-downloaded export (no cookie / no network needed) —
# useful to sanity-check the parser against a real file:
python -m pipeline.ingest --symbol RELIANCE --from-file data/RELIANCE.xlsx
```

## Tests
```bash
pytest
```
The parser is covered against a synthetic screener‑shaped workbook, so it can
be validated without a live login.

## Layout
```
pipeline/
  config.py            settings from .env
  db.py                SQLAlchemy engine/session
  models.py            schema (raw line items + computed tables)
  nifty50.py           constituents → symbol + sector
  screener_client.py   cookie auth, company-id discovery, Excel download
  parser.py            .xlsx "Data Sheet" → tidy line items
  ingest.py            one company: download → parse → store  (CLI)
tests/                 parser tests
docker-compose.yml     Postgres for local dev
```

## Project status / roadmap
- [x] **M1** Scaffold, DB schema, Nifty 50 list, docker-compose
- [x] **M2** One company end‑to‑end (download → parse → store), tests
- [ ] **M3** Ingest all 50 + daily scheduler
- [ ] **M4** Compute: normalization, overall + sector ranks, best competitor, red flags
- [ ] **M5** Claude 3‑year summary
- [ ] **M6** FastAPI endpoints
- [ ] **M7** React dashboard
- [ ] **M8** Deploy
