import json
import logging
from bot.config import settings

from google.oauth2.service_account import Credentials
import gspread

_gc_cache = None
_creds_cache = None


def get_credentials():
    global _creds_cache
    if _creds_cache is not None:
        return _creds_cache
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/calendar",
    ]
    raw = settings.google_creds_json.strip()
    if raw:
        try:
            info = json.loads(raw)
        except json.JSONDecodeError:
            import base64
            info = json.loads(base64.b64decode(raw).decode("utf-8"))
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        logging.info("Google auth: usando GOOGLE_CREDENTIALS (env var)")
    else:
        creds = Credentials.from_service_account_file(settings.credentials_file, scopes=scopes)
        logging.info(f"Google auth: usando archivo {settings.credentials_file}")
    _creds_cache = creds
    return creds


def get_gc():
    global _gc_cache
    if _gc_cache is not None:
        return _gc_cache
    _gc_cache = gspread.authorize(get_credentials())
    return _gc_cache


def get_calendar_service():
    from googleapiclient.discovery import build
    return build("calendar", "v3", credentials=get_credentials())


def reset_auth_cache():
    global _gc_cache, _creds_cache
    _gc_cache = None
    _creds_cache = None
