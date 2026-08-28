import math
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from backend.config import LOCATION, SOURCES
from backend.fetchers import FetchResult

SOURCE = "weather"

FMI_URL = "https://opendata.fmi.fi/wfs"
FMI_QUERY = "fmi::forecast::harmonie::surface::point::timevaluepair"

NS = {
    "gml": "http://www.opengis.net/gml/3.2",
    "wml2": "http://www.opengis.net/waterml/2.0",
}

# FMI:n weathersymbol3-koodit suomeksi (ilmatieteenlaitos.fi/latauspalvelun-pikaohje).
# +100 = yöversio samasta säästä, joten koodi normalisoidaan modulo 100:lla.
WEATHER_SYMBOLS = {
    1: "Selkeää", 2: "Puolipilvistä", 3: "Pilvistä",
    21: "Heikkoja sadekuuroja", 22: "Sadekuuroja", 23: "Voimakkaita sadekuuroja",
    31: "Heikkoa vesisadetta", 32: "Vesisadetta", 33: "Voimakasta vesisadetta",
    41: "Heikkoja lumikuuroja", 42: "Lumikuuroja", 43: "Voimakkaita lumikuuroja",
    51: "Heikkoa lumisadetta", 52: "Lumisadetta", 53: "Voimakasta lumisadetta",
    61: "Ukkoskuuroja", 62: "Voimakkaita ukkoskuuroja",
    63: "Ukkosta", 64: "Voimakasta ukkosta",
    71: "Heikkoja räntäkuuroja", 72: "Räntäkuuroja", 73: "Voimakkaita räntäkuuroja",
    81: "Heikkoa räntäsadetta", 82: "Räntäsadetta", 83: "Voimakasta räntäsadetta",
    91: "Utua", 92: "Sumua",
}


def _describe(code: float | None) -> str:
    if code is None or math.isnan(code):
        return ""
    return WEATHER_SYMBOLS.get(int(round(code)) % 100, "")


def _parse_series(root: ET.Element, param_name: str) -> dict[str, float]:
    """Poimii yhden parametrin aikasarjan {ISO-aika (UTC): arvo} XML-vastauksesta."""
    series: dict[str, float] = {}
    for ts in root.findall(".//wml2:MeasurementTimeseries", NS):
        gml_id = ts.get("{http://www.opengis.net/gml/3.2}id", "")
        if not gml_id.endswith(f"-{param_name}"):
            continue
        for tvp in ts.findall(".//wml2:MeasurementTVP", NS):
            time_el = tvp.find("wml2:time", NS)
            value_el = tvp.find("wml2:value", NS)
            if time_el is None or value_el is None or not time_el.text or not value_el.text:
                continue
            try:
                value = float(value_el.text)
            except ValueError:
                continue
            if math.isnan(value):
                continue
            series[time_el.text] = value
    return series


async def fetch() -> list[FetchResult]:
    cfg = SOURCES.get("weather", {})
    if not cfg.get("enabled", True):
        return []

    lat = LOCATION["lat"]
    lon = LOCATION["lon"]
    tz = ZoneInfo(LOCATION.get("timezone", "Europe/Helsinki"))

    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=1)
    end = now + timedelta(hours=62)

    url = (
        f"{FMI_URL}?service=WFS&version=2.0.0&request=getFeature"
        f"&storedquery_id={FMI_QUERY}"
        f"&latlon={lat},{lon}"
        f"&parameters=temperature,windspeedms,weathersymbol3,precipitation1h"
        f"&starttime={start.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f"&endtime={end.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)

    temps = _parse_series(root, "temperature")
    winds = _parse_series(root, "windspeedms")
    symbols = _parse_series(root, "weathersymbol3")
    precip = _parse_series(root, "precipitation1h")

    results = []

    # Nykyhetki: lähin tuleva/nykyinen aikaleima
    times_sorted = sorted(temps.keys())
    current_time = next((t for t in times_sorted if t >= now.strftime("%Y-%m-%dT%H:%M:%SZ")), None)
    if current_time is None and times_sorted:
        current_time = times_sorted[-1]

    if current_time:
        temp = temps.get(current_time)
        wind = winds.get(current_time)
        desc = _describe(symbols.get(current_time))
        results.append(
            FetchResult(
                source=SOURCE,
                title=f"{desc} {temp:.1f}°C".strip(),
                detail=f"Tuuli {wind:.1f} m/s" if wind is not None else "",
                priority="normal",
            )
        )

    # Päiväkohtaiset yhteenvedot: huominen + ylihuominen (paikallista aikaa)
    today_local = now.astimezone(tz).date()
    by_day: dict[str, list[str]] = {}
    for iso_time in temps:
        local_date = datetime.fromisoformat(iso_time.replace("Z", "+00:00")).astimezone(tz).date()
        if local_date <= today_local:
            continue
        by_day.setdefault(local_date.isoformat(), []).append(iso_time)

    for day in sorted(by_day.keys())[:2]:
        day_times = by_day[day]
        day_temps = [temps[t] for t in day_times if t in temps]
        day_precip = sum(precip.get(t, 0) for t in day_times)
        if not day_temps:
            continue
        # Säätila keskipäivältä (klo 12 paikallista aikaa) jos löytyy, muuten ensimmäinen
        midday_time = next(
            (t for t in day_times if datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(tz).hour == 12),
            day_times[0],
        )
        day_desc = _describe(symbols.get(midday_time))
        results.append(
            FetchResult(
                source=SOURCE,
                title=f"{day}: {day_desc}".strip(),
                detail=f"{min(day_temps):.0f}…{max(day_temps):.0f}°C, sade {day_precip:.1f} mm",
            )
        )

    return results
