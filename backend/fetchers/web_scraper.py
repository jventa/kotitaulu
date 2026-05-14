import httpx
from bs4 import BeautifulSoup

from backend.config import SCRAPINGBEE_API_KEY, SOURCES
from backend.fetchers import FetchResult

SOURCE = "web_scraper"

HEADERS = {"User-Agent": "Mozilla/5.0 (kotitaulu/1.0)"}
SCRAPINGBEE_URL = "https://app.scrapingbee.com/api/v1/"


async def _get_html(client: httpx.AsyncClient, url: str, render_js: bool) -> str | None:
    if render_js:
        if not SCRAPINGBEE_API_KEY:
            raise ValueError("SCRAPINGBEE_API_KEY puuttuu .env-tiedostosta")
        resp = await client.get(
            SCRAPINGBEE_URL,
            params={"api_key": SCRAPINGBEE_API_KEY, "url": url, "render_js": "true"},
        )
    else:
        resp = await client.get(url)
    return resp.text if resp.status_code == 200 else None


async def fetch() -> list[FetchResult]:
    cfg = SOURCES.get("web_scrapers", {})
    if not cfg.get("enabled", False):
        return []

    results = []
    async with httpx.AsyncClient(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for site in cfg.get("sites", []):
            url = site.get("url")
            selector = site.get("selector")
            title = site.get("title", url)
            max_items = site.get("max_items", 3)
            render_js = site.get("render_js", False)

            if not url or not selector:
                continue

            html = await _get_html(client, url, render_js)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            for el in soup.select(selector)[:max_items]:
                text = el.get_text(strip=True)
                link = el.get("href") or (el.find("a") or {}).get("href")
                results.append(
                    FetchResult(
                        source=SOURCE,
                        title=text,
                        detail=title,
                        url=link,
                    )
                )
    return results
