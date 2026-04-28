"""Allowlist guards used as decorators on every handler."""
from __future__ import annotations

from functools import wraps
from typing import Awaitable, Callable

from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes

from .supabase_client import Repo


HandlerFn = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]


def _user_id(update: Update) -> int | None:
    if update.effective_user is None:
        return None
    return update.effective_user.id


def require_allowed(handler: HandlerFn) -> HandlerFn:
    """Block calls from users who aren't in `allowed_users`."""

    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        repo: Repo = context.application.bot_data["repo"]
        user_id = _user_id(update)
        if user_id is None:
            return
        allowed = repo.get_allowed(user_id)
        if not allowed:
            logger.info("Denying user {} (not on allowlist)", user_id)
            if update.effective_message:
                await update.effective_message.reply_text(
                    "You are not allowed to use this bot. Contact the admin to be added."
                )
            return
        context.user_data["role"] = allowed.role
        await handler(update, context)

    return wrapper


def require_admin(handler: HandlerFn) -> HandlerFn:
    """Block calls from users who aren't admin."""

    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        repo: Repo = context.application.bot_data["repo"]
        user_id = _user_id(update)
        if user_id is None:
            return
        allowed = repo.get_allowed(user_id)
        if not allowed or allowed.role != "admin":
            logger.info("Denying user {} (not admin)", user_id)
            if update.effective_message:
                await update.effective_message.reply_text("Admin only.")
            return
        context.user_data["role"] = allowed.role
        await handler(update, context)

    return wrapper


def is_admin(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return context.user_data.get("role") == "admin"
