from __future__ import annotations

from loguru import logger
from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from ..auth import require_allowed
from ..config import Settings
from ..elevenlabs import ElevenLabsSignup
from ..format import (
    escape_md,
    render_account_success,
    render_failure,
    render_progress,
)
from ..menu import post_create_menu, retry_menu
from ..tempmail_client import TempMailClient
from ..supabase_client import Repo
from ..workflow import TOTAL_STEPS, create_account


async def _run(update: Update, context: ContextTypes.DEFAULT_TYPE, *, anchor: Message) -> None:
    settings: Settings = context.application.bot_data["settings"]
    repo: Repo = context.application.bot_data["repo"]
    tempmail: TempMailClient = context.application.bot_data["tempmail"]
    elevenlabs: ElevenLabsSignup = context.application.bot_data["elevenlabs"]

    user_id = update.effective_user.id

    async def progress(step: int, total: int, label: str) -> None:
        try:
            await anchor.edit_text(
                render_progress(step, total, label),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except BadRequest as exc:
            logger.debug("progress edit ignored: {}", exc)

    await progress(1, TOTAL_STEPS, "Starting…")

    result = await create_account(
        settings=settings,
        repo=repo,
        tempmail=tempmail,
        elevenlabs=elevenlabs,
        telegram_user_id=user_id,
        progress=progress,
    )

    if result.success:
        body = render_account_success(
            email=result.account.email,
            mailbox_password=result.account.mailbox_password,
            elevenlabs_password=result.account.elevenlabs_password,
            pinmx_login_url=settings.pinmx_login_url,
        )
        await anchor.edit_text(
            body,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=post_create_menu(),
            disable_web_page_preview=True,
        )
    else:
        await anchor.edit_text(
            render_failure(TOTAL_STEPS, TOTAL_STEPS, result.error or "unknown error"),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=retry_menu(),
        )


@require_allowed
async def cmd_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    anchor = await update.effective_message.reply_text(
        escape_md("Starting…"), parse_mode=ParseMode.MARKDOWN_V2
    )
    await _run(update, context, anchor=anchor)


@require_allowed
async def cb_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    anchor = query.message
    await anchor.edit_text(escape_md("Starting…"), parse_mode=ParseMode.MARKDOWN_V2)
    await _run(update, context, anchor=anchor)
