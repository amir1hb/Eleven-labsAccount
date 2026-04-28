"""Account-creation workflow.

This is the orchestration brain that ties together PinMX, Playwright, and
Supabase. It exposes two entry points:

- create_account()      — single account, with progress callback
- bulk_create_accounts() — sequential batch with throttling

The progress callback is invoked at each step so the calling Telegram
handler can edit the user's message in place.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from loguru import logger

from .config import Settings
from .elevenlabs import ElevenLabsSignup, extract_verify_url
from .generators import (
    pick_domain,
    random_password,
    random_usa_male_first_name,
    random_username,
)
from .pinmx import PinmxClient, PinmxError
from .supabase_client import Account, Repo


TOTAL_STEPS = 5

ProgressCb = Callable[[int, int, str], Awaitable[None]]


@dataclass
class CreateResult:
    account: Account
    success: bool
    error: str | None = None


async def _noop_progress(step: int, total: int, label: str) -> None:
    return None


async def create_account(
    *,
    settings: Settings,
    repo: Repo,
    pinmx: PinmxClient,
    elevenlabs: ElevenLabsSignup,
    telegram_user_id: int,
    progress: ProgressCb | None = None,
) -> CreateResult:
    """Create one ElevenLabs account end-to-end."""
    cb = progress or _noop_progress

    # ---- step 1: create PinMX mailbox -------------------------------------
    await cb(1, TOTAL_STEPS, "Generating mailbox at PinMX…")
    domain = pick_domain(settings.pinmx_domains) or settings.pinmx_domains[0]
    username = random_username()
    mailbox_password = random_password()
    elevenlabs_password = random_password()
    onboarding_first_name = random_usa_male_first_name()
    email = f"{username}@{domain}"

    tried: set[str] = set()
    while True:
        try:
            await pinmx.create_mailbox(
                domain=domain,
                username=username,
                password=mailbox_password,
                mark=str(telegram_user_id),
            )
            break
        except PinmxError as exc:
            tried.add(domain)
            logger.warning(
                "PinMX create_mailbox failed for {}: code={} msg={}",
                email,
                exc.code,
                exc.msg,
            )
            next_domain = pick_domain(settings.pinmx_domains, skip=tried)
            if not next_domain:
                # Insert a 'failed' row so it shows up in /list and stats.
                account = repo.insert_pending_account(
                    email=email,
                    mailbox_password=mailbox_password,
                    elevenlabs_password=elevenlabs_password,
                    domain=domain,
                    created_by=telegram_user_id,
                )
                repo.mark_failed(account.id, f"PinMX: {exc.msg}")
                return CreateResult(
                    account=account,
                    success=False,
                    error=f"PinMX rejected all domains: {exc.msg}",
                )
            domain = next_domain
            username = random_username()
            email = f"{username}@{domain}"

    # ---- step 1b: persist pending row ------------------------------------
    account = repo.insert_pending_account(
        email=email,
        mailbox_password=mailbox_password,
        elevenlabs_password=elevenlabs_password,
        domain=domain,
        created_by=telegram_user_id,
    )

    # ---- step 2: ElevenLabs signup ---------------------------------------
    await cb(2, TOTAL_STEPS, "Submitting elevenlabs.io signup…")
    try:
        async with elevenlabs.fresh_context() as context:
            page = await context.new_page()
            await elevenlabs.submit_signup(
                page,
                email=email,
                password=elevenlabs_password,
            )

            # ---- step 3: poll PinMX for verification email ---------------
            await cb(3, TOTAL_STEPS, "Waiting for verification email…")
            verify_url = await _wait_for_verify_link(
                pinmx=pinmx,
                mark=str(telegram_user_id),
                target_email=email,
                timeout_seconds=settings.verify_timeout_seconds,
            )
            if not verify_url:
                raise TimeoutError(
                    f"No verification email received in {settings.verify_timeout_seconds}s"
                )

            # Open verify link in a NEW TAB and run verify + sign-in + onboarding
            # all on that tab.
            verify_page = await context.new_page()
            try:
                # ---- step 4: verify modal + sign-in --------------------
                await cb(4, TOTAL_STEPS, "Verifying & signing in…")
                await elevenlabs.complete_verification(
                    verify_page,
                    verify_url=verify_url,
                    email=email,
                    password=elevenlabs_password,
                )

                # ---- step 5: onboarding wizard --------------------------
                await cb(5, TOTAL_STEPS, "Completing onboarding…")
                await elevenlabs.complete_onboarding(
                    verify_page, first_name=onboarding_first_name
                )
            finally:
                await verify_page.close()

        repo.mark_active(account.id)
        account.status = "active"
        return CreateResult(account=account, success=True)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc) or exc.__class__.__name__
        logger.exception("Workflow failed for account {}: {}", account.id, msg)
        repo.mark_failed(account.id, msg)
        return CreateResult(account=account, success=False, error=msg)


async def _wait_for_verify_link(
    *,
    pinmx: PinmxClient,
    mark: str,
    target_email: str,
    timeout_seconds: int,
    poll_interval: float = 5.0,
) -> str | None:
    """Poll PinMX inbox until we find the ElevenLabs verification email."""
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        try:
            messages = await pinmx.list_messages(mark=mark, limit=20)
        except PinmxError as exc:
            logger.warning("PinMX list_messages error: {}", exc)
            await asyncio.sleep(poll_interval)
            continue

        for message in messages:
            # Filter to messages addressed to this mailbox (mark may be reused
            # across multiple mailboxes when many accounts share a telegram id).
            if message.to_addr and target_email.lower() not in message.to_addr.lower():
                continue
            url = extract_verify_url(message.body)
            if url:
                return url
        await asyncio.sleep(poll_interval)
    return None


# ---- bulk -------------------------------------------------------------------


@dataclass
class BulkRow:
    index: int
    email: str | None
    success: bool
    error: str | None


async def bulk_create_accounts(
    *,
    settings: Settings,
    repo: Repo,
    pinmx: PinmxClient,
    elevenlabs: ElevenLabsSignup,
    telegram_user_id: int,
    count: int,
    on_row: Callable[[BulkRow], Awaitable[None]] | None = None,
) -> list[BulkRow]:
    """Run create_account `count` times sequentially with throttle.

    `on_row` is invoked after each completion so the caller can edit a
    running progress message in Telegram.
    """
    if count < 1 or count > settings.bulk_max:
        raise ValueError(f"count must be between 1 and {settings.bulk_max}")

    results: list[BulkRow] = []
    for i in range(1, count + 1):
        result = await create_account(
            settings=settings,
            repo=repo,
            pinmx=pinmx,
            elevenlabs=elevenlabs,
            telegram_user_id=telegram_user_id,
        )
        row = BulkRow(
            index=i,
            email=result.account.email,
            success=result.success,
            error=result.error,
        )
        results.append(row)
        if on_row:
            await on_row(row)

        if i < count:
            await asyncio.sleep(settings.bulk_throttle_seconds)
    return results
