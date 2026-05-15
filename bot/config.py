import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    token: str = field(default_factory=lambda: os.getenv("TOKEN", ""))
    chat_id: str = field(default_factory=lambda: os.getenv("CHAT_ID", ""))
    chat_id_esposa: str = field(default_factory=lambda: os.getenv("CHAT_ID_ESPOSA", ""))
    timezone: str = field(default_factory=lambda: os.getenv("TIMEZONE", "America/Argentina/Buenos_Aires"))
    sheet_id: str = field(default_factory=lambda: os.getenv("SHEET_ID", ""))
    calendar_id: str = field(default_factory=lambda: os.getenv("CALENDAR_ID", "primary"))
    credentials_file: str = field(default_factory=lambda: os.getenv("CREDENTIALS_FILE", "credentials.json"))
    google_creds_json: str = field(default_factory=lambda: os.getenv("GOOGLE_CREDENTIALS", ""))
    openai_key: str = field(default_factory=lambda: os.getenv("OPENAI_KEY", ""))

    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    openai_max_tokens: int = field(default_factory=lambda: int(os.getenv("OPENAI_MAX_TOKENS", "500")))
    openai_max_tool_rounds: int = field(default_factory=lambda: int(os.getenv("OPENAI_MAX_TOOL_ROUNDS", "5")))

    max_conversation_history: int = field(default_factory=lambda: int(os.getenv("MAX_CONVERSATION_HISTORY", "12")))

    notification_hour: int = field(default_factory=lambda: int(os.getenv("NOTIFICATION_HOUR", "9")))
    notification_minute: int = field(default_factory=lambda: int(os.getenv("NOTIFICATION_MINUTE", "0")))
    weekly_summary_day: str = field(default_factory=lambda: os.getenv("WEEKLY_SUMMARY_DAY", "sun"))
    weekly_summary_hour: int = field(default_factory=lambda: int(os.getenv("WEEKLY_SUMMARY_HOUR", "9")))
    weekly_summary_minute: int = field(default_factory=lambda: int(os.getenv("WEEKLY_SUMMARY_MINUTE", "0")))

    payments_reminder_window_days: int = field(default_factory=lambda: int(os.getenv("PAYMENTS_WINDOW_DAYS", "3")))

    briefing_hour: int = field(default_factory=lambda: int(os.getenv("BRIEFING_HOUR", "8")))
    briefing_minute: int = field(default_factory=lambda: int(os.getenv("BRIEFING_MINUTE", "0")))

    inactivity_alert_days: int = field(default_factory=lambda: int(os.getenv("INACTIVITY_ALERT_DAYS", "3")))
    inactivity_alert_hour: int = field(default_factory=lambda: int(os.getenv("INACTIVITY_ALERT_HOUR", "10")))
    inactivity_alert_minute: int = field(default_factory=lambda: int(os.getenv("INACTIVITY_ALERT_MINUTE", "0")))

    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


settings = Settings()
