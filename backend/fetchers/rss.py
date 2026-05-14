import feedparser

from backend.config import SOURCES
from backend.fetchers import FetchResult

SOURCE = "rss"


async def fetch() -> list[FetchResult]:
    cfg = SOURCES.get("rss", {})
    if not cfg.get("enabled", True):
        return []

    results = []
    for feed_cfg in cfg.get("feeds", []):
        url = feed_cfg.get("url")
        feed_title = feed_cfg.get("title", url)
        max_items = feed_cfg.get("max_items", 5)

        parsed = feedparser.parse(url)
        for entry in parsed.entries[:max_items]:
            pub = entry.get("published", entry.get("updated"))
            results.append(
                FetchResult(
                    source=SOURCE,
                    title=entry.get("title", "(ei otsikkoa)"),
                    detail=feed_title,
                    time=pub,
                    url=entry.get("link"),
                )
            )
    return results
