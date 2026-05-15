import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env")

# HA add-on: /data on addon:n oma persistentti tallennustila, /config on HA:n config-kansio
_IS_ADDON = os.path.exists("/data/options.json")
_DATA_DIR = Path("/data") if _IS_ADDON else _ROOT
_CONFIG_DIR = Path("/config") if _IS_ADDON else _ROOT

_addon_opts: dict = {}
if _IS_ADDON:
    import json as _json
    with open("/data/options.json") as _f:
        _addon_opts = _json.load(_f)

_config_path = _CONFIG_DIR / "app_config.yaml"
if not _config_path.exists():
    _config_path = _DATA_DIR / "app_config.yaml"
if not _config_path.exists():
    _config_path = _ROOT / "app_config.yaml"

with open(_config_path) as f:
    _cfg = yaml.safe_load(f)


def _get(key: str, default=None):
    return os.getenv(key, default)


# HA add-on saa automaattisesti supervisor-tokenin ja käyttää sisäistä API-osoitetta
if _IS_ADDON:
    HA_URL: str = "http://supervisor/core"
    HA_TOKEN: str = (
        os.getenv("SUPERVISOR_TOKEN")
        or os.getenv("HASSIO_TOKEN")
        or _addon_opts.get("ha_token", "")
    )
else:
    HA_URL: str = _get("HA_URL", "http://homeassistant.local:8123")
    HA_TOKEN: str = _get("HA_TOKEN", "")

# Google-tiedostot luetaan /config/:sta (HA:n config-kansio, mapattuna addon:iin)
_google_token_file = _addon_opts.get("google_token_file", _get("GOOGLE_TOKEN_FILE", "token.json"))
_google_creds_file = _addon_opts.get("google_credentials_file", _get("GOOGLE_CREDENTIALS_FILE", "credentials.json"))
GOOGLE_CREDENTIALS_FILE: str = str(_CONFIG_DIR / _google_creds_file)
GOOGLE_TOKEN_FILE: str = str(_CONFIG_DIR / _google_token_file)

SCRAPINGBEE_API_KEY: str = _addon_opts.get("scrapingbee_api_key") or _get("SCRAPINGBEE_API_KEY", "")
FLARESOLVERR_URL: str = _addon_opts.get("flaresolverr_url") or _get("FLARESOLVERR_URL", "")

LOCATION: dict = _cfg.get("location", {"lat": 60.1699, "lon": 24.9384, "timezone": "Europe/Helsinki"})
SCHEDULER: dict = _cfg.get("scheduler", {"daily_refresh_hour": 6, "daily_refresh_minute": 0})
SOURCES: dict = _cfg.get("sources", {})

DB_PATH: str = str(_DATA_DIR / "kotitaulu.db")
