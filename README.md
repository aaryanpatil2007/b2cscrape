# LeadFlow Accelerator Scraper

A production-ready web app that scrapes **B2C consumer companies** from top accelerators (Y Combinator, a16z Speedrun, PearX), filters for companies that would genuinely need marketing, and provides a lead management dashboard for outreach tracking.

## Features

- **Smart B2C Filtering** — Keyword + category-based detection keeps only consumer-facing companies (marketplaces, social apps, fintech for individuals, edtech, gaming, health/wellness, etc.) and filters out B2B/enterprise/infra
- **Multi-Source Scraping** — Playwright-based scrapers for YC Companies, a16z Speedrun, and PearX portfolios with headless toggle, retries, and anti-timeout handling
- **Recency Filter** — Dropdown to select 1–10 year intervals, filtering by batch/founded date
- **Lead Dashboard** — Dark-mode React UI with search, accelerator/batch/status filters, outreach checkboxes, and per-company notes
- **Deduplication** — Unique constraint on (name, accelerator) prevents duplicate entries across scrapes
- **PostgreSQL Persistence** — Companies table + outreach logs table with full CRUD API

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React (Vite) + Tailwind CSS + Lucide Icons |
| Backend | Python FastAPI + SQLAlchemy ORM |
| Scraping | Playwright (Chromium, headless) |
| Database | PostgreSQL 16 |
| Container | Docker + Docker Compose |

## Quick Start

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |

1. Open http://localhost:3000
2. Click **Configure** to select sources and year range
3. Click **Run Scraper** to scrape B2C companies
4. Use filters, checkboxes, and notes to manage outreach

## Project Structure

```
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py                  # FastAPI app entry point
│       ├── config.py                # Environment settings
│       ├── database.py              # SQLAlchemy engine + session
│       ├── models.py                # Company + OutreachLog tables
│       ├── schemas.py               # Pydantic request/response models
│       ├── routers/
│       │   ├── companies.py         # CRUD + filters + outreach logs
│       │   └── scraper.py           # POST /api/scrape with dedup
│       └── scrapers/
│           ├── base.py              # BaseScraper (Playwright + retries)
│           ├── consumer_filter.py   # Shared B2C detection logic
│           ├── yc.py                # Y Combinator scraper
│           ├── a16z.py              # a16z Speedrun scraper
│           └── pearx.py             # PearX / Pear VC scraper
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/
        ├── App.jsx                  # Main layout + state
        ├── api/client.js            # API client
        └── components/
            ├── ScrapePanel.jsx      # Source selection + run button
            ├── FilterBar.jsx        # Search + dropdown filters
            ├── CompanyTable.jsx     # Lead table with outreach toggle
            └── NotesModal.jsx       # Per-company notes editor
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/scrape/` | Run scrapers with source/year/headless config |
| `GET` | `/api/companies/` | List companies (filterable by accelerator, batch, status, search) |
| `GET` | `/api/companies/filters` | Get available filter options |
| `PATCH` | `/api/companies/{id}` | Update outreach status or notes |
| `DELETE` | `/api/companies/all` | Clear all company data |
| `POST` | `/api/companies/outreach-log` | Add outreach log entry |
| `GET` | `/api/companies/{id}/outreach-logs` | Get outreach history |

## Important Notes

- **Anti-Bot Protection**: YC uses Cloudflare. If blocked, consider adding `playwright-stealth` or residential proxies.
- **Email Enrichment**: Accelerator sites don't list founder emails. Use scraped websites/LinkedIn with Hunter.io, Apollo.io, or RocketReach for email discovery.
- **Schema Migrations**: For production schema changes, integrate [Alembic](https://alembic.sqlalchemy.org/).
