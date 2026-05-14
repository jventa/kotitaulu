"""
Aja kerran Google OAuth -valtuutuksen saamiseksi:
    python -m backend.auth_setup
"""
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from backend.config import GOOGLE_CREDENTIALS_FILE, GOOGLE_TOKEN_FILE

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def main() -> None:
    creds_path = Path(GOOGLE_CREDENTIALS_FILE)
    if not creds_path.exists():
        print(f"Tiedostoa {creds_path} ei löydy.")
        print("Lataa se Google Cloud Consolesta (OAuth 2.0 Client ID, Desktop app).")
        return

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    creds = flow.run_local_server(port=0)

    with open(GOOGLE_TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    print(f"Token tallennettu: {GOOGLE_TOKEN_FILE}")


if __name__ == "__main__":
    main()
