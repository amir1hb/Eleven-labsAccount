"""👥 Admin — manage allowlist (add/remove/list users)."""
from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..auth import require_admin
from ..format import escape_md
from ..menu import admin_menu, back_to_menu
from ..supabase_client import Repo


def _format_users(repo: Repo) -> str:
    users = repo.list_allowed()
    if not users:
        return "No users on the allowlist."
    lines = [f"Allowed users ({len(users)}):"]
    for u in users:
        lines.append(f"• {u.telegram_user_id} ({u.role})")
    return "\n".join(lines)


# ---- slash commands ---------------------------------------------------------


@require_admin
async def cmd_add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/add_user <id> [role]"""
    repo: Repo = context.application.bot_data["repo"]
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /add_user <id> [user|admin]")
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await update.effective_message.reply_text("ID must be an integer.")
        return
    role = args[1] if len(args) > 1 else "user"
    if role not in {"user", "admin"}:
        await update.effective_message.reply_text("Role must be `user` or `admin`.")
        return
    repo.upsert_allowed(target_id, role=role, added_by=update.effective_user.id)
    await update.effective_message.reply_text(f"Added {target_id} as {role}.")


@require_admin
async def cmd_remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/remove_user <id>"""
    repo: Repo = context.application.bot_data["repo"]
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /remove_user <id>")
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await update.effective_message.reply_text("ID must be an integer.")
        return
    if target_id == update.effective_user.id:
        await update.effective_message.reply_text("Refusing to remove yourself.")
        return
    removed = repo.remove_allowed(target_id)
    if removed:
        await update.effective_message.reply_text(f"Removed {target_id}.")
    else:
        await update.effective_message.reply_text(f"{target_id} was not on the allowlist.")


@require_admin
async def cmd_list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    repo: Repo = context.application.bot_data["repo"]
    text = escape_md(_format_users(repo))
    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=admin_menu()
    )


# ---- callback (👥 Manage Users button) -------------------------------------


@require_admin
async def cb_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    repo: Repo = context.application.bot_data["repo"]
    text = escape_md(_format_users(repo))
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=admin_menu()
    )


@require_admin
async def cb_admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data["pending_admin_action"] = "add"
    await query.edit_message_text(
        escape_md("Send the new user as `<id> [user|admin]`. Example: `67890 user`."),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_to_menu(),
    )


@require_admin
async def cb_admin_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data["pending_admin_action"] = "remove"
    await query.edit_message_text(
        escape_md("Send the user id to remove. Example: `67890`."),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_to_menu(),
    )


@require_admin
async def text_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catches the next plain-text reply after Add/Remove."""
    pending = context.user_data.pop("pending_admin_action", None)
    if not pending:
        return  # not in admin mode; let other handlers (or no-op) handle it
    repo: Repo = context.application.bot_data["repo"]
    text = (update.effective_message.text or "").strip()
    parts = text.split()
    if not parts:
        await update.effective_message.reply_text("Empty input.")
        return
    try:
        target_id = int(parts[0])
    except ValueError:
        await update.effective_message.reply_text("First token must be a numeric Telegram id.")
        return

    if pending == "add":
        role = parts[1] if len(parts) > 1 else "user"
        if role not in {"user", "admin"}:
            await update.effective_message.reply_text("Role must be `user` or `admin`.")
            return
        repo.upsert_allowed(target_id, role=role, added_by=update.effective_user.id)
        await update.effective_message.reply_text(
            f"Added {target_id} as {role}.", reply_markup=admin_menu()
        )
    elif pending == "remove":
        if target_id == update.effective_user.id:
            await update.effective_message.reply_text("Refusing to remove yourself.")
            return
        if repo.remove_allowed(target_id):
            await update.effective_message.reply_text(
                f"Removed {target_id}.", reply_markup=admin_menu()
            )
        else:
            await update.effective_message.reply_text(
                f"{target_id} was not on the allowlist.", reply_markup=admin_menu()
            )
