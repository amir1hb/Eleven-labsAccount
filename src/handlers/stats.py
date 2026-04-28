"""/stats and 📊 Stats — small dashboard."""
from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..auth import is_admin, require_allowed
from ..format import escape_md
from ..menu import back_to_menu
from ..supabase_client import Repo


def _format_block(title: str, stats: dict[str, int]) -> list[str]:
    return [
        escape_md(title),
        escape_md(f"Today: {stats['today_total']} accounts ({stats['today_active']} ok, {stats['today_failed']} failed)"),
        escape_md(f"All time: {stats['total']} accounts ({stats['total_active']} ok, {stats['total_failed']} failed)"),
    ]


async def _render(update: Update, context: ContextTypes.DEFAULT_TYPE, *, edit: bool) -> None:
    repo: Repo = context.application.bot_data["repo"]
    user_id = update.effective_user.id
    admin = is_admin(context)

    lines = ["*Stats*", ""]
    my_stats = repo.stats(created_by=user_id)
    lines.extend(_format_block("You", my_stats))

    if admin:
        global_stats = repo.stats(created_by=None)
        lines.append("")
        lines.extend(_format_block("Global", global_stats))

    text = "\n".join(lines)
    keyboard = back_to_menu()
    if edit:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard
        )
    else:
        await update.effective_message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard
        )


@require_allowed
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context, edit=False)


@require_allowed
async def cb_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await _render(update, context, edit=True)
