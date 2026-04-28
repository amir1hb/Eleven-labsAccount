"""/bulk N and 📦 Bulk Create — sequential bulk creation with live progress."""
from __future__ import annotations

from loguru import logger
from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from ..auth import require_allowed
from ..config import Settings
from ..elevenlabs import ElevenLabsSignup
from ..format import escape_md
from ..menu import bulk_picker, post_create_menu
from ..pinmx import PinmxClient
from ..supabase_client import Repo
from ..workflow import BulkRow, bulk_create_accounts


async def _run_bulk(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    anchor: Message,
    count: int,
) -> None:
    settings: Settings = context.application.bot_data["settings"]
    repo: Repo = context.application.bot_data["repo"]
    pinmx: PinmxClient = context.application.bot_data["pinmx"]
    elevenlabs: ElevenLabsSignup = context.application.bot_data["elevenlabs"]

    if count < 1 or count > settings.bulk_max:
        await anchor.edit_text(
            escape_md(f"N must be between 1 and {settings.bulk_max}."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    rows: list[str] = []

    async def render(done: int, ok: int, fail: int) -> None:
        header = (
            f"Creating {count} accounts…" if done < count else f"Done. {ok} ok, {fail} failed."
        )
        body = "\n".join(rows) if rows else ""
        text = escape_md(header) + (("\n\n" + escape_md(body)) if body else "")
        try:
            await anchor.edit_text(text, parse_mode=ParseMode.MARKDOWN_V2)
        except BadRequest as exc:
            logger.debug("bulk edit ignored: {}", exc)

    await render(done=0, ok=0, fail=0)

    ok_count = 0
    fail_count = 0

    async def on_row(row: BulkRow) -> None:
        nonlocal ok_count, fail_count
        if row.success:
            ok_count += 1
            rows.append(f"[{row.index}/{count}] ✅ {row.email}")
        else:
            fail_count += 1
            rows.append(f"[{row.index}/{count}] ❌ {row.email or '<no email>'} — {row.error or 'failed'}")
        await render(done=row.index, ok=ok_count, fail=fail_count)

    await bulk_create_accounts(
        settings=settings,
        repo=repo,
        pinmx=pinmx,
        elevenlabs=elevenlabs,
        telegram_user_id=update.effective_user.id,
        count=count,
        on_row=on_row,
    )

    await anchor.edit_reply_markup(reply_markup=post_create_menu())


@require_allowed
async def cmd_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/bulk N` runs immediately. `/bulk` alone shows the picker."""
    args = context.args or []
    if not args:
        await update.effective_message.reply_text(
            "How many accounts to create?",
            reply_markup=bulk_picker(),
        )
        return

    try:
        count = int(args[0])
    except ValueError:
        await update.effective_message.reply_text(
            "Usage: /bulk <N>  (1-20)",
        )
        return

    anchor = await update.effective_message.reply_text(
        escape_md("Starting…"), parse_mode=ParseMode.MARKDOWN_V2
    )
    await _run_bulk(update, context, anchor=anchor, count=count)


@require_allowed
async def cb_bulk_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User tapped 📦 Bulk Create — show the size picker."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "How many accounts to create?",
        reply_markup=bulk_picker(),
    )


@require_allowed
async def cb_bulk_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User tapped a size button (e.g. `bulk:5`)."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    try:
        _, n = data.split(":", 1)
        count = int(n)
    except ValueError:
        await query.edit_message_text("Invalid count.")
        return
    anchor = query.message
    await anchor.edit_text(escape_md("Starting…"), parse_mode=ParseMode.MARKDOWN_V2)
    await _run_bulk(update, context, anchor=anchor, count=count)
