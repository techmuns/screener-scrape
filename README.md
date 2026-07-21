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
Screener company pages are **public**, so no login/cookie is needed.

```
 daily job ─► screener.in public company page (×50)
                    │
                    ▼
          parse HTML  ─►  Postgres  ◄─  compute: normalize · ranks ·
                    │                    similarity · red-flags · summary
                    ▼
                 FastAPI  ─►  React dashboard
```

| Layer      | Tech                         | Status |
|------------|------------------------------|--------|
| Pipeline   | Python (requests, BeautifulSoup, SQLAlchemy) | ✅ Milestones 1–2 |
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

### 1. Configure
```bash
cp .env.example .env
```
**No screener login is needed** — company pages are public. `.env` only holds the
database URL and (later) the Claude API key. It's gitignored and never committed.

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
# Fetch the live public page:
python -m pipeline.ingest --symbol RELIANCE

# Or parse a saved page (no network needed) — useful for testing:
python -m pipeline.ingest --symbol RELIANCE --from-file data/RELIANCE.html
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
  screener_client.py   fetch the public company page (no login)
  web_parser.py        company page HTML → tidy line items  (primary)
  parser.py            optional .xlsx export reader + shared data classes
  ingest.py            one company: fetch → parse → store  (CLI)
tests/                 parser tests (HTML + xlsx)
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
