"""/export and 📤 Export — picks format, sends file."""
from __future__ import annotations

from datetime import date
from io import BytesIO

from telegram import Update
from telegram.ext import ContextTypes

from ..auth import is_admin, require_allowed
from ..exporter import to_csv, to_txt
from ..menu import back_to_menu, export_format_picker
from ..supabase_client import Repo


@require_allowed
async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Choose a format:", reply_markup=export_format_picker()
    )


@require_allowed
async def cb_export_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Choose a format:", reply_markup=export_format_picker()
    )


@require_allowed
async def cb_export_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback `export:csv` or `export:txt`."""
    query = update.callback_query
    await query.answer()
    repo: Repo = context.application.bot_data["repo"]
    data = query.data or ""
    try:
        _, fmt = data.split(":", 1)
    except ValueError:
        await query.edit_message_text("Invalid format.")
        return

    fmt = fmt.lower()
    if fmt not in {"csv", "txt"}:
        await query.edit_message_text("Format must be CSV or TXT.")
        return

    user_id = update.effective_user.id
    accounts = repo.all_accounts(created_by=None if is_admin(context) else user_id)

    if not accounts:
        await query.edit_message_text(
            "No accounts to export.", reply_markup=back_to_menu()
        )
        return

    if fmt == "csv":
        payload = to_csv(accounts)
        filename = f"accounts-{date.today().isoformat()}.csv"
    else:
        payload = to_txt(accounts)
        filename = f"accounts-{date.today().isoformat()}.txt"

    bio = BytesIO(payload)
    bio.name = filename
    await query.message.reply_document(
        document=bio,
        filename=filename,
        caption=f"{len(accounts)} accounts",
    )
    # Restore the menu under the original message.
    await query.edit_message_text("Export sent.", reply_markup=back_to_menu())
