import base64
import email as email_lib

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from backend.config import GOOGLE_TOKEN_FILE, SOURCES
from backend.fetchers import FetchResult

SOURCE = "gmail"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _load_creds() -> Credentials:
    creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


async def fetch() -> list[FetchResult]:
    cfg = SOURCES.get("gmail", {})
    if not cfg.get("enabled", True):
        return []

    max_results = cfg.get("max_results", 10)
    query = cfg.get("query", "is:unread is:important")

    creds = _load_creds()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    response = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()

    results = []
    for msg_ref in response.get("messages", []):
        msg = service.users().messages().get(
            userId="me", id=msg_ref["id"], format="metadata",
            metadataHeaders=["Subject", "From"]
        ).execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "(ei aihetta)")
        sender = headers.get("From", "")
        results.append(
            FetchResult(
                source=SOURCE,
                title=subject,
                detail=sender,
                url=f"https://mail.google.com/mail/u/0/#inbox/{msg_ref['id']}",
                priority="high" if "IMPORTANT" in msg.get("labelIds", []) else "normal",
            )
        )
    return results
