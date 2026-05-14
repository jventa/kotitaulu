# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Käynnistys

```bash
pip install -r requirements.txt
cp .env.example .env           # täytä HA_TOKEN
python -m backend.auth_setup   # kerran: Google OAuth (kalenteri + gmail)
uvicorn backend.main:app --reload
```

Avaa `http://localhost:8000`. Pakota haku: `curl -X POST http://localhost:8000/api/refresh`.

## Arkkitehtuuri

**Python FastAPI** -backend + **vanilla JS** -frontend. Ei frameworkkia frontendissä.

```
backend/
  main.py          — FastAPI-app, mounts frontend/ static files, lifespan käynnistää schedulerin
  scheduler.py     — APScheduler + run_all_fetchers() (kutsuu kaikkia fetchereitä)
  storage.py       — aiosqlite; save_items(source, items) korvaa kaikki saman lähteen rivit
  config.py        — lataa .env + config.yaml, exporttaa vakiot (HA_URL, SOURCES, LOCATION…)
  auth_setup.py    — kerran ajettava Google OAuth -helper
  fetchers/
    __init__.py        — FetchResult-dataclass (to_dict())
    google_calendar.py — Google Calendar API v3, hakee SOURCES.google_calendar.days_ahead päivää
    gmail.py           — Gmail API, hakee SOURCES.gmail.query -hakuehdon mukaan
    home_assistant.py  — HA REST API; entiteetit + todo-listat config.yaml:sta
    weather.py         — Open-Meteo (ei API-avainta), palauttaa nykyhetken + 2 seuraavaa päivää
    rss.py             — feedparser, syötteet config.yaml:sta
    stocks.py          — yfinance, symbolit config.yaml:sta
    web_scraper.py     — httpx + BeautifulSoup, per-site CSS-selector config.yaml:sta
frontend/
  index.html / app.js / style.css
```

### Tietovuo

1. `scheduler.py:run_all_fetchers()` kutsuu jokaista fetcheriä
2. Jokainen fetcher palauttaa `list[FetchResult]`
3. `storage.save_items(source, items)` **poistaa ensin** kaikki ko. lähteen vanhat rivit, sitten insertoi uudet
4. `GET /api/items` lukee SQLitestä ja ryhmittelee lähteittäin → `{sources: {source: [items]}}`
5. `app.js` renderöi kortit, auto-refresh 60 s

### Uuden fetcherin lisääminen

1. Luo `backend/fetchers/myfetcher.py` — toteuta `async def fetch() -> list[FetchResult]`
2. Lisää rivi `_FETCHERS`-listaan `scheduler.py`:ssä
3. Lisää asetukset `config.yaml`:n `sources:`-osioon ja lue ne `config.SOURCES`:sta

## Endpointit

| Metodi | Polku | Kuvaus |
|--------|-------|--------|
| GET | `/api/items` | Kaikki tallennetut kohteet ryhmiteltyinä lähteittäin |
| POST | `/api/refresh` | Käynnistää kaikkien fetchereiden haun välittömästi |
| GET | `/health` | Liveness-tarkistus |

## Konfiguraatio

`config.yaml` — lähteiden on/off, RSS-syötteet, HA-entiteetit, sijainti, ajastusaika.  
`.env` — salaisuudet: `HA_TOKEN`, Google-tiedostopolut.

## Google OAuth

Luo `credentials.json` Google Cloud Consolessa (OAuth 2.0 Client ID, tyyppi "Desktop app"). Ota käyttöön **Google Calendar API** ja **Gmail API**. Aja `python -m backend.auth_setup` → tallentaa `token.json`. Token uusiutuu automaattisesti.
