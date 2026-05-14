from datetime import datetime

import httpx

from backend.config import LOCATION, SOURCES
from backend.fetchers import FetchResult

SOURCE = "weather"

WMO_CODES = {
    0: "Selkeää", 1: "Pääosin selkeää", 2: "Puolipilvistä", 3: "Pilvistä",
    45: "Sumua", 48: "Jäätävää sumua",
    51: "Tihkusadetta", 53: "Tihkusadetta", 55: "Tihkusadetta",
    61: "Sadetta", 63: "Sadetta", 65: "Kovaa sadetta",
    71: "Lumisadetta", 73: "Lumisadetta", 75: "Kovaa lumisadetta",
    80: "Sadekuuroja", 81: "Sadekuuroja", 82: "Voimakkaita sadekuuroja",
    95: "Ukkosta", 96: "Ukkosta", 99: "Kovaa ukkosta",
}


async def fetch() -> list[FetchResult]:
    cfg = SOURCES.get("weather", {})
    if not cfg.get("enabled", True):
        return []

    lat = LOCATION["lat"]
    lon = LOCATION["lon"]
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,weathercode,windspeed_10m"
        f"&daily=temperature_2m_max,temperature_2m_min,weathercode,precipitation_sum"
        f"&timezone={LOCATION.get('timezone', 'Europe/Helsinki')}"
        f"&forecast_days=3"
    )

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    results = []
    current = data.get("current", {})
    temp = current.get("temperature_2m")
    code = current.get("weathercode", 0)
    wind = current.get("windspeed_10m")
    desc = WMO_CODES.get(code, "")
    results.append(
        FetchResult(
            source=SOURCE,
            title=f"{desc} {temp}°C",
            detail=f"Tuuli {wind} km/h",
            priority="normal",
        )
    )

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    for i, d in enumerate(dates[1:3], 1):  # huominen + ylihuominen
        max_t = daily["temperature_2m_max"][i]
        min_t = daily["temperature_2m_min"][i]
        wcode = daily["weathercode"][i]
        precip = daily["precipitation_sum"][i]
        day_desc = WMO_CODES.get(wcode, "")
        results.append(
            FetchResult(
                source=SOURCE,
                title=f"{d}: {day_desc}",
                detail=f"{min_t}…{max_t}°C, sade {precip} mm",
            )
        )

    return results
