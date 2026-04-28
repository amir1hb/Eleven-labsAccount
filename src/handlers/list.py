"""/list and 📋 My Accounts — paginated list, tap row to re-show creds."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..auth import is_admin, require_allowed
from ..config import Settings
from ..format import escape_md, humanise_when, render_account_success
from ..menu import (
    CB_LIST_DETAIL_PREFIX,
    CB_LIST_PAGE_PREFIX,
    back_to_menu,
    list_pagination,
)
from ..supabase_client import Repo


def _status_glyph(status: str) -> str:
    return {"active": "✅", "failed": "❌", "pending": "⏳"}.get(status, "?")


async def _render_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    page: int,
    edit: bool,
) -> None:
    settings: Settings = context.application.bot_data["settings"]
    repo: Repo = context.application.bot_data["repo"]
    user_id = update.effective_user.id

    created_by = None if is_admin(context) else user_id
    accounts, total = repo.list_accounts(
        created_by=created_by,
        page=page,
        page_size=settings.list_page_size,
    )

    if total == 0:
        text = escape_md("You have no accounts yet. Tap 🤖 Create Account to start.")
        keyboard = back_to_menu()
        if edit:
            await update.callback_query.edit_message_text(
                text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard
            )
        else:
            await update.effective_message.reply_text(
                text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard
            )
        return

    total_pages = max(1, (total + settings.list_page_size - 1) // settings.list_page_size)
    header = f"Your accounts ({total}) · page {page}/{total_pages}"
    if is_admin(context):
        header = f"All accounts ({total}) · page {page}/{total_pages}"

    lines = [escape_md(header), ""]
    detail_buttons: list[list[InlineKeyboardButton]] = []
    base_index = (page - 1) * settings.list_page_size
    for offset, account in enumerate(accounts, start=1):
        idx = base_index + offset
        line = f"{idx}. {_status_glyph(account.status)} {account.email} · {humanise_when(account.created_at)}"
        lines.append(escape_md(line))
        detail_buttons.append(
            [
                InlineKeyboardButton(
                    f"{idx}. {account.email}",
                    callback_data=f"{CB_LIST_DETAIL_PREFIX}{account.id}",
                )
            ]
        )

    nav_keyboard = list_pagination(page=page, total_pages=total_pages)
    rows = detail_buttons + list(nav_keyboard.inline_keyboard)
    keyboard = InlineKeyboardMarkup(rows)

    text = "\n".join(lines)
    if edit:
        await update.callback_query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    else:
        await update.effective_message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )


@require_allowed
async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_page(update, context, page=1, edit=False)


@require_allowed
async def cb_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`list:<page>` callback."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    try:
        _, p = data.split(":", 1)
        page = max(1, int(p))
    except ValueError:
        page = 1
    await _render_page(update, context, page=page, edit=True)


@require_allowed
async def cb_show(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`show:<account_id>` — re-render full credentials for one account."""
    query = update.callback_query
    await query.answer()
    settings: Settings = context.application.bot_data["settings"]
    repo: Repo = context.application.bot_data["repo"]
    data = query.data or ""
    try:
        _, account_id = data.split(":", 1)
    except ValueError:
        await query.edit_message_text("Invalid selection.")
        return

    account = repo.get_account(account_id)
    if not account:
        await query.edit_message_text("Account not found.")
        return

    # Owner-only access (admin sees all).
    if not is_admin(context) and account.created_by != update.effective_user.id:
        await query.edit_message_text("Not your account.")
        return

    body = render_account_success(
        email=account.email,
        mailbox_password=account.mailbox_password,
        elevenlabs_password=account.elevenlabs_password,
        pinmx_login_url=settings.pinmx_login_url,
    )
    await query.edit_message_text(
        body,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Back to list", callback_data=f"{CB_LIST_PAGE_PREFIX}1"
                    ),
                    InlineKeyboardButton("Menu", callback_data="menu"),
                ]
            ]
        ),
        disable_web_page_preview=True,
    )
