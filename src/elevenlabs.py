"""ElevenLabs signup automation via Playwright.

ElevenLabs has no public signup API — we drive the web form. All selectors
live in this file (single source of truth for selector drift). If the page
markup changes, tweak `Selectors` and the navigation steps below.

Tip for selector verification:
    playwright codegen https://elevenlabs.io/sign-up
"""
from __future__ import annotations

import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from loguru import logger
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from .kameleo import KameleoBackend


# ---- selectors --------------------------------------------------------------


@dataclass(frozen=True)
class Selectors:
    """Centralised selectors for the elevenlabs.io signup + verify flow.

    Primary selectors use `data-testid` (most stable). Each tuple has
    fallbacks if the primary breaks; first match wins.
    """

    # Sign-up form ----------------------------------------------------------
    signup_email_input: tuple[str, ...] = (
        '[data-testid="sign-up-email-input"]',
        'input[name="email"]',
        'input[type="email"]',
    )
    signup_password_input: tuple[str, ...] = (
        '[data-testid="sign-up-password-input"]',
        'input[name="password"]',
        'input[type="password"]',
    )
    signup_submit_button: tuple[str, ...] = (
        '[data-testid="signup-signup-button-div"] button',
        'button:has-text("Sign up")',
        'button[type="submit"]',
    )

    # Indicators that signup form was accepted (usually "check your email").
    post_submit_success: tuple[str, ...] = (
        'text=/check your email/i',
        'text=/verify/i',
        'text=/confirm/i',
    )

    # Verify-tab modal ------------------------------------------------------
    # After clicking the verify link, ElevenLabs shows a dialog:
    #   "Almost there! Please sign in once more with the same credentials …"
    # We click the dialog's Continue button to proceed to the sign-in page.
    verify_modal: tuple[str, ...] = (
        'div[role="dialog"][data-state="open"]',
        'div[role="dialog"]',
    )
    verify_continue_button: tuple[str, ...] = (
        'div[role="dialog"] button:has-text("Continue")',
        'button:has-text("Continue")',
    )

    # Sign-in form ----------------------------------------------------------
    signin_email_input: tuple[str, ...] = (
        '[data-testid="sign-in-email-input"]',
        '#sign-in-form input[name="email"]',
        'input[name="email"]',
    )
    signin_password_input: tuple[str, ...] = (
        '[data-testid="sign-in-password-input"]',
        '#sign-in-form input[name="password"]',
        'input[name="password"]',
    )
    signin_submit_button: tuple[str, ...] = (
        '[data-testid="sign-in-submit-button"]',
        '#sign-in-form button[type="submit"]',
        'button[type="submit"]',
    )

    # Onboarding wizard -----------------------------------------------------
    # 1) /app/onboarding lands → click "Continue"
    # 2) firstname + agree checkbox + Next
    # 3) Skip × 3 (last screen has both "Skip" and "Explore all plans")
    # 4) Land on /app/speech-synthesis/text-to-speech (or /app/home)
    onboarding_continue_button: tuple[str, ...] = (
        'button:text-is("Continue")',
        'button:has-text("Continue")',
    )
    onboarding_firstname_input: tuple[str, ...] = (
        'input[name="firstname"]',
        '#firstname',
        'input[autocomplete="given-name"]',
    )
    onboarding_agree_checkbox: tuple[str, ...] = (
        'button[role="checkbox"]',
        '[role="checkbox"]',
    )
    onboarding_next_button: tuple[str, ...] = (
        'button[type="submit"]:has-text("Next")',
        'button:text-is("Next")',
    )
    # `:text-is("Skip")` is exact-match so it never matches "Explore all plans".
    onboarding_skip_button: tuple[str, ...] = (
        'button:text-is("Skip")',
    )

    # The final URL we wait for after onboarding completes.
    onboarding_done_url_pattern: str = (
        r"https?://[^/]*elevenlabs\.io/app/(speech-synthesis|home)"
    )


SELECTORS = Selectors()

VERIFY_URL_PATTERNS = [
    re.compile(r"https?://[^\s\"'<>]+elevenlabs\.io/[^\s\"'<>]*verify[^\s\"'<>]*", re.IGNORECASE),
    re.compile(r"https?://[^\s\"'<>]+elevenlabs\.io/[^\s\"'<>]*confirm[^\s\"'<>]*", re.IGNORECASE),
]


def extract_verify_url(email_body: str) -> str | None:
    """Find the ElevenLabs verification URL in an email body (HTML or text)."""
    if not email_body:
        return None
    for pattern in VERIFY_URL_PATTERNS:
        match = pattern.search(email_body)
        if match:
            # Strip trailing punctuation that might have leaked in.
            url = match.group(0).rstrip(").,;]>'\"")
            return url
    return None


# ---- driver ----------------------------------------------------------------


class ElevenLabsSignup:
    """Drives elevenlabs.io/sign-up using either Playwright Chromium or Kameleo.

    Backend selection:
      - `kameleo=None`  → launch a single shared Chromium instance, fresh
        context per signup.
      - `kameleo=<KameleoBackend>` → fresh Kameleo profile per signup
        (best anti-detect; per-signup latency is higher).
    """

    def __init__(
        self,
        *,
        headless: bool,
        signup_url: str,
        kameleo: KameleoBackend | None = None,
    ):
        self._headless = headless
        self._signup_url = signup_url
        self._kameleo = kameleo
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None  # only used in non-Kameleo mode

    async def __aenter__(self) -> "ElevenLabsSignup":
        self._playwright = await async_playwright().start()
        if self._kameleo is None:
            self._browser = await self._playwright.chromium.launch(headless=self._headless)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    @asynccontextmanager
    async def fresh_context(self) -> AsyncIterator[BrowserContext]:
        """Yield a fresh browser context for one signup."""
        if self._playwright is None:
            raise RuntimeError("ElevenLabsSignup not started; use `async with`")

        if self._kameleo is not None:
            async with self._kameleo_context() as context:
                yield context
        else:
            async with self._chromium_context() as context:
                yield context

    @asynccontextmanager
    async def _chromium_context(self) -> AsyncIterator[BrowserContext]:
        if self._browser is None:
            raise RuntimeError("Chromium browser not initialised")
        context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        try:
            yield context
        finally:
            await context.close()

    @asynccontextmanager
    async def _kameleo_context(self) -> AsyncIterator[BrowserContext]:
        assert self._kameleo is not None
        assert self._playwright is not None
        profile_id = await self._kameleo.create_and_start_profile()
        browser: Browser | None = None
        try:
            cdp_url = self._kameleo.cdp_url(profile_id)
            logger.info("Connecting Playwright to Kameleo profile {}", profile_id)
            browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
            # Kameleo profiles come up with a default context.
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            yield context
        finally:
            if browser is not None:
                try:
                    await browser.close()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("playwright close after Kameleo: {}", exc)
            await self._kameleo.stop_and_delete_profile(profile_id)

    async def submit_signup(
        self,
        page: Page,
        *,
        email: str,
        password: str,
        full_name: str = "",
    ) -> None:
        """Fill the signup form (email + password) and submit it.

        The submit button starts `disabled` and is enabled by client-side
        validation once the password meets criteria. Playwright's `click`
        waits for actionability, so it auto-waits for the button to enable.
        """
        logger.info("Navigating to {}", self._signup_url)
        await page.goto(self._signup_url, wait_until="domcontentloaded")

        await _fill_first_match(page, SELECTORS.signup_email_input, email)
        await _fill_first_match(page, SELECTORS.signup_password_input, password)

        # Click waits for the button to leave its initial `disabled` state.
        await _click_first_match(page, SELECTORS.signup_submit_button)

        try:
            await page.wait_for_selector(
                ",".join(SELECTORS.post_submit_success), timeout=15_000
            )
            logger.info("Signup form submitted; verification email expected")
        except Exception:
            logger.debug("No explicit post-submit banner; assuming submission succeeded")

    async def complete_verification(
        self,
        verify_page: Page,
        *,
        verify_url: str,
        email: str,
        password: str,
    ) -> None:
        """Navigate `verify_page` (an already-opened new tab) through:

            verify URL → "Continue" modal → sign-in form → /app/onboarding

        Raises if sign-in does not redirect away from /sign-in within timeout.
        """
        logger.info("Opening verify link in verify tab: {}", verify_url)
        await verify_page.goto(verify_url, wait_until="domcontentloaded")

        # ElevenLabs verify URL shows a dialog asking the user to sign in again.
        # If no modal appears (some accounts skip it), fall through.
        try:
            await verify_page.wait_for_selector(
                ",".join(SELECTORS.verify_modal),
                state="visible",
                timeout=10_000,
            )
            logger.info("Verify modal shown; clicking Continue")
            await _click_first_match(verify_page, SELECTORS.verify_continue_button)
        except Exception:
            logger.debug("No verify modal; will attempt sign-in directly")

        # Sign-in form should render either via modal redirect or directly.
        await _fill_first_match(
            verify_page, SELECTORS.signin_email_input, email, timeout=20_000
        )
        await _fill_first_match(verify_page, SELECTORS.signin_password_input, password)
        await _click_first_match(verify_page, SELECTORS.signin_submit_button)

        # Wait until we leave the sign-in page (typically lands on /app/onboarding).
        try:
            await verify_page.wait_for_url(
                lambda url: "/sign-in" not in url and "/sign-up" not in url,
                timeout=30_000,
            )
        except Exception:
            raise RuntimeError(
                f"Sign-in did not complete (still on {verify_page.url})"
            )
        logger.info("Sign-in succeeded — at {}", verify_page.url)

    async def complete_onboarding(
        self,
        page: Page,
        *,
        first_name: str,
    ) -> None:
        """Walk through the post-signin onboarding wizard.

        Phases (per spec):
          1. /app/onboarding shows a "Continue" button → click it.
          2. firstname input + agree-to-terms checkbox + "Next".
          3. "Skip".
          4. "Skip".
          5. plans page with "Skip" and "Explore all plans" → click "Skip".
          6. land on /app/speech-synthesis/text-to-speech (or /app/home).
        """
        logger.info("Onboarding: starting (initial URL = {})", page.url)

        # Phase 1: initial Continue.
        await _click_first_match(
            page, SELECTORS.onboarding_continue_button, timeout=20_000
        )
        logger.debug("Onboarding: clicked initial Continue")

        # Phase 2: firstname + agree + Next.
        await _fill_first_match(
            page, SELECTORS.onboarding_firstname_input, first_name, timeout=20_000
        )
        # The agree control is a Radix `<button role="checkbox">`, not an <input>.
        # Click toggles its checked state.
        await _click_first_match(
            page, SELECTORS.onboarding_agree_checkbox, timeout=10_000
        )
        await _click_first_match(
            page, SELECTORS.onboarding_next_button, timeout=10_000
        )
        logger.debug("Onboarding: name + agree + Next done")

        # Phases 3–5: three Skip clicks. Each Skip is on its own page; we
        # wait for the next "Skip" to render before clicking it. Tolerant
        # of an extra step appearing or missing — logs and continues.
        skip_attempts = 3
        for i in range(1, skip_attempts + 1):
            try:
                await page.wait_for_selector(
                    SELECTORS.onboarding_skip_button[0],
                    state="visible",
                    timeout=20_000,
                )
                await _click_first_match(
                    page, SELECTORS.onboarding_skip_button, timeout=5_000
                )
                logger.debug("Onboarding: Skip #{} clicked", i)
            except Exception as exc:
                logger.warning("Onboarding: Skip #{} failed: {}", i, exc)
                # Don't abort — we may have already advanced past this step.

        # Phase 6: wait for the final landing URL.
        try:
            await page.wait_for_url(
                re.compile(SELECTORS.onboarding_done_url_pattern),
                timeout=20_000,
            )
            logger.info("Onboarding complete — landed on {}", page.url)
        except Exception:
            if "/onboarding" in page.url:
                raise RuntimeError(
                    f"Onboarding incomplete — still on {page.url}"
                )
            logger.debug(
                "Onboarding final URL not strictly matched but past /onboarding ({})",
                page.url,
            )


# ---- helpers ----------------------------------------------------------------


async def _fill_first_match(page: Page, selectors: tuple[str, ...], value: str, *, timeout: int = 10_000) -> None:
    last_error: Exception | None = None
    for sel in selectors:
        try:
            await page.wait_for_selector(sel, timeout=timeout, state="visible")
            await page.fill(sel, value)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
    raise RuntimeError(f"No element matched selectors {selectors!r}: {last_error}")


async def _click_first_match(page: Page, selectors: tuple[str, ...], *, timeout: int = 10_000) -> None:
    last_error: Exception | None = None
    for sel in selectors:
        try:
            await page.wait_for_selector(sel, timeout=timeout, state="visible")
            await page.click(sel)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
    raise RuntimeError(f"No clickable element matched {selectors!r}: {last_error}")


async def _check_first_match(page: Page, selectors: tuple[str, ...], *, timeout: int = 5_000) -> None:
    last_error: Exception | None = None
    for sel in selectors:
        try:
            await page.wait_for_selector(sel, timeout=timeout)
            await page.check(sel)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
    raise RuntimeError(f"No checkbox matched {selectors!r}: {last_error}")
