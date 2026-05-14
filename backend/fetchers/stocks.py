from datetime import datetime

import yfinance as yf

from backend.config import SOURCES
from backend.fetchers import FetchResult

SOURCE = "stocks"


async def fetch() -> list[FetchResult]:
    cfg = SOURCES.get("stocks", {})
    if not cfg.get("enabled", True):
        return []

    results = []
    for symbol in cfg.get("symbols", []):
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = getattr(info, "last_price", None)
        prev = getattr(info, "previous_close", None)
        currency = getattr(info, "currency", "")

        if price is None:
            continue

        change_pct = ((price - prev) / prev * 100) if prev else 0
        sign = "+" if change_pct >= 0 else ""
        priority = "high" if abs(change_pct) >= 5 else "normal"

        results.append(
            FetchResult(
                source=SOURCE,
                title=symbol,
                detail=f"{price:.2f} {currency}  ({sign}{change_pct:.2f}%)",
                priority=priority,
            )
        )
    return results
