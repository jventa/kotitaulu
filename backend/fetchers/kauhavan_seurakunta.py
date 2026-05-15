import re
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import httpx

from backend.config import FLARESOLVERR_URL, SCRAPINGBEE_API_KEY
from backend.fetchers import FetchResult

SOURCE = "kauhavan_seurakunta"
URL = "https://www.kauhavanseurakunta.fi/tapahtumat/"
TZ = ZoneInfo("Europe/Helsinki")
SCRAPINGBEE_URL = "https://app.scrapingbee.com/api/v1/"


def _parse_date(date_str: str) -> date | None:
    """'ke 13.5.' → date"""
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.", date_str)
    if not m:
        return None
    day, month = int(m.group(1)), int(m.group(2))
    year = date.today().year
    try:
        d = date(year, month, day)
    except ValueError:
        return None
    if (d - date.today()).days < -180:
        d = date(year + 1, month, day)
    return d


def _parse_time(time_str: str) -> str | None:
    """'klo\\n  9.00' → '09:00'"""
    m = re.search(r"(\d{1,2})\.(\d{2})", time_str)
    if not m:
        return None
    return f"{int(m.group(1)):02d}:{m.group(2)}"


async def _get_html() -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        if FLARESOLVERR_URL:
            resp = await client.post(
                f"{FLARESOLVERR_URL.rstrip('/')}/v1",
                json={"cmd": "request.get", "url": URL, "maxTimeout": 60000},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "ok":
                return data["solution"]["response"]
        resp = await client.get(
            SCRAPINGBEE_URL,
            params={
                "api_key": SCRAPINGBEE_API_KEY,
                "url": URL,
                "render_js": "true",
                "premium_proxy": "true",
                "wait": "3000",
            },
        )
        resp.raise_for_status()
        return resp.text


async def fetch() -> list[FetchResult]:
    today = date.today()
    tomorrow = today + timedelta(days=1)
    target_dates = {today, tomorrow}

    html = await _get_html()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    results = []
    for item in soup.select("a.event-search-listview-item"):
        date_el = item.select_one("span.event-date")
        if not date_el:
            continue

        event_date = _parse_date(date_el.get_text())
        if event_date not in target_dates:
            continue

        title_el = item.select_one(".event-item-header")
        title = title_el.get_text(strip=True) if title_el else "(ei otsikkoa)"

        time_el = item.select_one("span.event-time")
        time_str = _parse_time(time_el.get_text()) if time_el else None

        desc_el = item.select_one(".event-item-description")
        description = desc_el.get_text(strip=True) if desc_el else None

        # Sijainti: event-item-metadata sisältää päivämäärän + kellon + paikan
        loc_text = ""
        meta_el = item.select_one(".event-item-metadata")
        if meta_el:
            full = meta_el.get_text(" ", strip=True)
            # Poista päivämäärä, kellonaika ja mahdollinen loppuaika (– HH.MM)
            loc_text = re.sub(r"^[\w\s\d\.]+klo\s+[\d\.]+(\s*[–-]\s*[\d\.]+)?\s*", "", full).strip()

        detail_parts = [p for p in [loc_text, description] if p]
        detail = " — ".join(detail_parts) if detail_parts else None

        iso_time = None
        if time_str:
            iso_time = f"{event_date.isoformat()}T{time_str}:00"

        results.append(
            FetchResult(
                source=SOURCE,
                title=title,
                detail=detail,
                time=iso_time,
                url=item.get("href"),
            )
        )

    return results
