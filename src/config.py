"""Environment configuration loaded from .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _csv(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    admin_telegram_id: int

    pinmx_token: str
    pinmx_domains: List[str] = field(default_factory=lambda: ["pinmx.net", "pingmx.com"])

    supabase_url: str = ""
    supabase_service_key: str = ""

    headless: bool = True
    verify_timeout_seconds: int = 120
    bulk_throttle_seconds: int = 45
    bulk_max: int = 20
    list_page_size: int = 10

    # Browser backend
    browser_mode: str = "kameleo"  # "kameleo" or "playwright"
    kameleo_base_url: str = "http://localhost:5050"
    kameleo_device_type: str = "desktop"
    kameleo_browser_product: str = "chrome"
    kameleo_os_family: str = "windows"

    log_level: str = "INFO"

    pinmx_api_base: str = "https://open-api.pinmx.com"
    elevenlabs_signup_url: str = "https://elevenlabs.io/sign-up"
    elevenlabs_signin_url: str = "https://elevenlabs.io/app/sign-in"
    pinmx_login_url: str = "https://mail-client.pinmx.com"


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=_required("TELEGRAM_BOT_TOKEN"),
        admin_telegram_id=int(_required("ADMIN_TELEGRAM_ID")),
        pinmx_token=_required("PINMX_TOKEN"),
        pinmx_domains=_csv("PINMX_DOMAINS", ["pinmx.net", "pingmx.com"]),
        supabase_url=_required("SUPABASE_URL"),
        supabase_service_key=_required("SUPABASE_SERVICE_KEY"),
        headless=_bool("HEADLESS", True),
        verify_timeout_seconds=_int("VERIFY_TIMEOUT_SECONDS", 120),
        bulk_throttle_seconds=_int("BULK_THROTTLE_SECONDS", 45),
        bulk_max=_int("BULK_MAX", 20),
        list_page_size=_int("LIST_PAGE_SIZE", 10),
        browser_mode=os.getenv("BROWSER_MODE", "kameleo").strip().lower(),
        kameleo_base_url=os.getenv("KAMELEO_BASE_URL", "http://localhost:5050"),
        kameleo_device_type=os.getenv("KAMELEO_DEVICE_TYPE", "desktop"),
        kameleo_browser_product=os.getenv("KAMELEO_BROWSER_PRODUCT", "chrome"),
        kameleo_os_family=os.getenv("KAMELEO_OS_FAMILY", "windows"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
