from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from loguru import logger

from .config import Settings
from .elevenlabs import ElevenLabsSignup, extract_verify_url
from .generators import random_password, random_usa_male_first_name
from .tempmail_client import TempMailClient
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
    tempmail: TempMailClient,
    elevenlabs: ElevenLabsSignup,
    telegram_user_id: int,
    progress: ProgressCb | None = None,
) -> CreateResult:
    cb = progress or _noop_progress

    await cb(1, TOTAL_STEPS, "Generating mailbox at Temp-Mail…")
    try:
        mailbox_data = await tempmail.create_mailbox()
        email = mailbox_data["email"]
        token = mailbox_data["token"]
        domain = email.split("@")[1]
        logger.info(f"Temp-Mail mailbox created: {email}")
    except Exception as exc:
        account = repo.insert_pending_account(
            email="unknown@temp-mail.io",
            mailbox_password="",
            elevenlabs_password="",
            domain="temp-mail.io",
            created_by=telegram_user_id,
        )
        repo.mark_failed(account.id, f"Temp-Mail: {str(exc)}")
        return CreateResult(
            account=account,
            success=False,
            error=f"Temp-Mail mailbox creation failed: {str(exc)}",
        )

    elevenlabs_password = random_password()
    mailbox_password = "N/A"

    account = repo.insert_pending_account(
        email=email,
        mailbox_password=mailbox_password,
        elevenlabs_password=elevenlabs_password,
        domain=domain,
        created_by=telegram_user_id,
    )

    await cb(2, TOTAL_STEPS, "Submitting elevenlabs.io signup…")
    try:
        async with elevenlabs.fresh_context() as context:
            page = await context.new_page()
            await elevenlabs.submit_signup(
                page,
                email=email,
                password=elevenlabs_password,
            )

            await cb(3, TOTAL_STEPS, "Waiting for verification email…")
            verify_url = await _wait_for_verify_link(
                tempmail=tempmail,
                target_email=email,
                timeout_seconds=settings.verify_timeout_seconds,
            )
            if not verify_url:
                raise TimeoutError(
                    f"No verification email received in {settings.verify_timeout_seconds}s"
                )

            verify_page = await context.new_page()
            try:
                await cb(4, TOTAL_STEPS, "Verifying & signing in…")
                await elevenlabs.complete_verification(
                    verify_page,
                    verify_url=verify_url,
                    email=email,
                    password=elevenlabs_password,
                )

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
    tempmail: TempMailClient,
    target_email: str,
    timeout_seconds: int,
    poll_interval: float = 10.0,
) -> str | None:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        try:
            messages = await tempmail.list_messages()
        except Exception as exc:
            logger.warning("Temp-Mail list_messages error: {}", exc)
            await asyncio.sleep(poll_interval)
            continue

        for message in messages:
            body = message.get("body", "")
            url = extract_verify_url(body)
            if url:
                return url
        await asyncio.sleep(poll_interval)
    return None


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
    tempmail: TempMailClient,
    elevenlabs: ElevenLabsSignup,
    telegram_user_id: int,
    count: int,
    on_row: Callable[[BulkRow], Awaitable[None]] | None = None,
) -> list[BulkRow]:
    if count < 1 or count > settings.bulk_max:
        raise ValueError(f"count must be between 1 and {settings.bulk_max}")

    results: list[BulkRow] = []
    for i in range(1, count + 1):
        result = await create_account(
            settings=settings,
            repo=repo,
            tempmail=tempmail,
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
