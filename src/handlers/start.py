"""/start, /menu, /help handlers."""
from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..auth import is_admin, require_allowed
from ..menu import back_to_menu, main_menu


WELCOME = (
    "*Welcome\\!* 👋\n\n"
    "I create ElevenLabs accounts for you using fresh PinMX mailboxes\\.\n"
    "Tap a button below to get started\\."
)

HELP = (
    "*Commands*\n"
    "/create — make one ElevenLabs account\n"
    "/bulk — make several accounts in a row \\(up to 20\\)\n"
    "/list — list your accounts\n"
    "/stats — your dashboard\n"
    "/export — download your accounts as CSV or TXT\n"
    "/menu — show the main menu\n\n"
    "Admins also have:\n"
    "/add\\_user `<id> [role]` — allow a user\n"
    "/remove\\_user `<id>` — revoke access\n"
    "/list\\_users — show the allowlist"
)


@require_allowed
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        WELCOME,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_menu(is_admin=is_admin(context)),
    )


@require_allowed
async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Main menu",
        reply_markup=main_menu(is_admin=is_admin(context)),
    )


@require_allowed
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        HELP,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_to_menu(),
    )


@require_allowed
async def cb_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Re-render the main menu when a 'Menu' button is tapped."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Main menu",
        reply_markup=main_menu(is_admin=is_admin(context)),
    )


@require_allowed
async def cb_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        HELP,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_to_menu(),
    )
