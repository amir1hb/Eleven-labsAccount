"""Account-creation workflow.

This is the orchestration brain that ties together Guerrilla Mail, Playwright, and
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
from .generators import random_password, random_usa_male_first_name, random_username
from .guerrilla import GuerrillaMailClient  # ✅ تغییر
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
    guerrilla: GuerrillaMailClient,  # ✅ تغییر
    elevenlabs: ElevenLabsSignup,
    telegram_user_id: int,
    progress: ProgressCb | None = None,
) -> CreateResult:
    """Create one ElevenLabs account end-to-end."""
    cb = progress or _noop_progress

    # ---- step 1: create Guerrilla mailbox ---------------------------------
    await cb(1, TOTAL_STEPS, "Generating mailbox at Guerrilla Mail…")
    
    # ✅ ایجاد صندوق پستی با Guerrilla (بدون نیاز به دامنه و username خاص)
    try:
        mailbox_data = await guerrilla.create_mailbox()
        email = mailbox_data["email"]
        # استخراج دامنه از ایمیل (برای ذخیره در دیتابیس)
        domain = email.split("@")[1]
        logger.info(f"✅ Guerrilla mailbox created: {email}")
    except Exception as exc:
        # در صورت خطا، یک رکورد شکست‌خورده ثبت می‌کنیم
        account = repo.insert_pending_account(
            email="unknown@guerrillamail.com",
            mailbox_password="",  # Guerrilla پسورد ندارد
            elevenlabs_password="",
            domain="guerrillamail.com",
            created_by=telegram_user_id,
        )
        repo.mark_failed(account.id, f"Guerrilla: {str(exc)}")
        return CreateResult(
            account=account,
            success=False,
            error=f"Guerrilla mailbox creation failed: {str(exc)}",
        )

    # رمزهای عبور برای ElevenLabs و صندوق پستی (Guerrilla نیازی به پسورد ندارد)
    elevenlabs_password = random_password()
    # برای صندوق پستی، یک پسورد ساختگی برای دیتابیس می‌گذاریم (چون Guerrilla پسورد ندارد)
    mailbox_password = "N/A"

    # ---- step 1b: ذخیره رکورد در دیتابیس (وضعیت pending) ----------------
    account = repo.insert_pending_account(
        email=email,
        mailbox_password=mailbox_password,
        elevenlabs_password=elevenlabs_password,
        domain=domain,
        created_by=telegram_user_id,
    )

    # ---- step 2: submit ElevenLabs signup -------------------------------
    await cb(2, TOTAL_STEPS, "Submitting elevenlabs.io signup…")
    try:
        async with elevenlabs.fresh_context() as context:
            page = await context.new_page()
            await elevenlabs.submit_signup(
                page,
                email=email,
                password=elevenlabs_password,
            )

            # ---- step 3: poll Guerrilla for verification email -----------
            await cb(3, TOTAL_STEPS, "Waiting for verification email…")
            verify_url = await _wait_for_verify_link(
                guerrilla=guerrilla,  # ✅ تغییر
                target_email=email,
                timeout_seconds=settings.verify_timeout_seconds,
            )
            if not verify_url:
                raise TimeoutError(
                    f"No verification email received in {settings.verify_timeout_seconds}s"
                )

            # Open verify link in a NEW TAB and run verify + sign-in + onboarding
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
                onboarding_first_name = random_usa_male_first_name()
                await elevenlabs.complete_onboarding(
                    verify_page, first_name=onboarding_first_name
                )
            finally:
                await verify_page.close()

        repo.mark_active(account.id)
        account.status = "active"
        return CreateResult(account=account, success=True)
    except Exception as exc:
        msg = str(exc) or exc.__class__.__name__
        logger.exception("Workflow failed for account {}: {}", account.id, msg)
        repo.mark_failed(account.id, msg)
        return CreateResult(account=account, success=False, error=msg)


async def _wait_for_verify_link(
    *,
    guerrilla: GuerrillaMailClient,  # ✅ تغییر
    target_email: str,
    timeout_seconds: int,
    poll_interval: float = 5.0,
) -> str | None:
    """Poll Guerrilla inbox until we find the ElevenLabs verification email."""
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        try:
            messages = await guerrilla.list_messages()
        except Exception as exc:
            logger.warning("Guerrilla list_messages error: {}", exc)
            await asyncio.sleep(poll_interval)
            continue

        for message in messages:
            # Guerrilla messages may not have `to_addr`, but we can check
            # if the target email appears in the message (or just trust that
            # all messages are for this mailbox).
            # We can also check if the message body contains the verification link.
            # We'll just extract URL from body.
            body = message.get("body", "")
            url = extract_verify_url(body)
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
    guerrilla: GuerrillaMailClient,  # ✅ تغییر
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
            guerrilla=guerrilla,
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
