import datetime
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from backend.config import GOOGLE_CREDENTIALS_FILE, GOOGLE_TOKEN_FILE, LOCATION, SOURCES
from backend.fetchers import FetchResult

SOURCE = "google_calendar"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _load_creds() -> Credentials:
    creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


async def fetch() -> list[FetchResult]:
    cfg = SOURCES.get("google_calendar", {})
    if not cfg.get("enabled", True):
        return []

    days_ahead = cfg.get("days_ahead", 7)
    tz = ZoneInfo(LOCATION.get("timezone", "Europe/Helsinki"))
    now = datetime.datetime.now(tz)
    time_min = now.isoformat()
    time_max = (now + datetime.timedelta(days=days_ahead)).isoformat()

    creds = _load_creds()
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    calendars = service.calendarList().list().execute().get("items", [])

    seen_ids = set()
    results = []
    for cal in calendars:
        cal_id = cal["id"]
        events_result = (
            service.events()
            .list(
                calendarId=cal_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        for event in events_result.get("items", []):
            event_id = event.get("id")
            if event_id in seen_ids:
                continue
            seen_ids.add(event_id)
            start = event["start"].get("dateTime", event["start"].get("date"))
            results.append(
                FetchResult(
                    source=SOURCE,
                    title=event.get("summary", "(ei otsikkoa)"),
                    detail=event.get("location") or event.get("description"),
                    time=start,
                    url=event.get("htmlLink"),
                )
            )

    results.sort(key=lambda r: r.time or "")
    return results
