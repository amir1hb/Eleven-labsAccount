"""Kameleo backend for anti-detect browser launches.

Each signup gets a fresh profile (= fresh fingerprint). Profile lifecycle:
    create  → start → use via Playwright CDP → stop → delete

Uses the official `kameleo.local-api-client` SDK (sync) wrapped in
`asyncio.to_thread` so it plays nicely with the rest of the async stack.
"""
from __future__ import annotations

import asyncio
import secrets
from urllib.parse import urlparse

from loguru import logger

# Import lazily so the bot still runs in `playwright` browser mode without
# needing the Kameleo SDK installed.
try:
    from kameleo.local_api_client import KameleoLocalApiClient  # type: ignore
    from kameleo.local_api_client.models import (  # type: ignore
        BrowserSettings,
        CreateProfileRequest,
    )

    _SDK_AVAILABLE = True
except Exception:  # noqa: BLE001
    _SDK_AVAILABLE = False
    KameleoLocalApiClient = None  # type: ignore
    BrowserSettings = None  # type: ignore
    CreateProfileRequest = None  # type: ignore


class KameleoBackend:
    """Manages per-signup Kameleo profile lifecycle."""

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:5050",
        device_type: str = "desktop",
        browser_product: str = "chrome",
        os_family: str = "windows",
        browser_arguments: list[str] | None = None,
    ):
        if not _SDK_AVAILABLE:
            raise RuntimeError(
                "kameleo.local-api-client is not installed. "
                "Add it to your environment to use BROWSER_MODE=kameleo."
            )
        self._base_url = base_url.rstrip("/")
        self._device_type = device_type
        self._browser_product = browser_product
        self._os_family = os_family
        self._browser_arguments = list(browser_arguments or [])
        self._client = KameleoLocalApiClient(endpoint=self._base_url)

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def host(self) -> str:
        parsed = urlparse(self._base_url)
        return parsed.netloc or "localhost:5050"

    def cdp_url(self, profile_id: str) -> str:
        """Playwright CDP endpoint for a running Kameleo profile."""
        return f"ws://{self.host}/playwright/{profile_id}"

    # ---- async wrappers around the sync SDK -----------------------------

    async def _to_thread(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    async def self_check(self) -> None:
        """Ping fingerprint search to verify Kameleo CLI is reachable."""
        fingerprints = await self._to_thread(
            self._client.fingerprint.search_fingerprints,
            device_type=self._device_type,
            browser_product=self._browser_product,
            os_family=self._os_family,
        )
        if not fingerprints:
            raise RuntimeError(
                f"Kameleo returned no fingerprints for device={self._device_type} "
                f"browser={self._browser_product} os={self._os_family}"
            )
        logger.info(
            "Kameleo self-check OK ({} fingerprints available)", len(fingerprints)
        )

    async def create_and_start_profile(self) -> str:
        """Create a fresh profile and start it. Returns profile id."""
        fingerprints = await self._to_thread(
            self._client.fingerprint.search_fingerprints,
            device_type=self._device_type,
            browser_product=self._browser_product,
            os_family=self._os_family,
        )
        if not fingerprints:
            raise RuntimeError("Kameleo: no fingerprints available")

        chosen = secrets.choice(fingerprints)
        request = CreateProfileRequest(
            fingerprint_id=chosen.id,
            name=f"bot-{secrets.token_hex(4)}",
        )
        profile = await self._to_thread(self._client.profile.create_profile, request)
        logger.debug("Kameleo profile {} created (fp={})", profile.id, chosen.id)

        settings = BrowserSettings(arguments=self._browser_arguments)
        await self._to_thread(self._client.profile.start_profile, profile.id, settings)
        logger.debug("Kameleo profile {} started", profile.id)

        return profile.id

    async def stop_and_delete_profile(self, profile_id: str) -> None:
        """Best-effort cleanup. Errors are logged, not raised."""
        try:
            await self._to_thread(self._client.profile.stop_profile, profile_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Kameleo stop_profile({}) failed: {}", profile_id, exc)
        try:
            await self._to_thread(self._client.profile.delete_profile, profile_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Kameleo delete_profile({}) failed: {}", profile_id, exc)
