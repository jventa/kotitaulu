import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend import config
from backend.fetchers import FetchResult
from backend.storage import log_fetch, save_items

logger = logging.getLogger(__name__)

_FETCHERS = [
    ("google_calendar", "backend.fetchers.google_calendar"),
    ("gmail", "backend.fetchers.gmail"),
    ("home_assistant", "backend.fetchers.home_assistant"),
    ("weather", "backend.fetchers.weather"),
    ("rss", "backend.fetchers.rss"),
    ("stocks", "backend.fetchers.stocks"),
    ("web_scraper", "backend.fetchers.web_scraper"),
    ("kauhavan_seurakunta", "backend.fetchers.kauhavan_seurakunta"),
]


async def run_all_fetchers() -> dict[str, int]:
    import importlib

    counts: dict[str, int] = {}
    for name, module_path in _FETCHERS:
        try:
            module = importlib.import_module(module_path)
            items: list[FetchResult] = await module.fetch()
            await save_items(name, [i.to_dict() for i in items])
            await log_fetch(name, "ok", f"{len(items)} items")
            counts[name] = len(items)
            logger.info("Fetched %d items from %s", len(items), name)
        except Exception as exc:
            await log_fetch(name, "error", str(exc))
            logger.error("Fetcher %s failed: %s", name, exc)
            counts[name] = 0
    return counts


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    hour = config.SCHEDULER.get("daily_refresh_hour", 6)
    minute = config.SCHEDULER.get("daily_refresh_minute", 0)
    scheduler.add_job(run_all_fetchers, "cron", hour=hour, minute=minute)
    return scheduler
