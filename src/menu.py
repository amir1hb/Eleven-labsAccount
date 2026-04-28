"""Inline keyboard layouts. Single source of truth for button labels & callback data."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ---- callback data namespace -----------------------------------------------
# Keep callback strings short and stable — they are persisted in the message.

CB_MENU = "menu"
CB_HELP = "help"

CB_CREATE = "create"
CB_BULK = "bulk"
CB_BULK_PREFIX = "bulk:"          # bulk:<n>

CB_LIST = "list"
CB_LIST_PAGE_PREFIX = "list:"     # list:<page>
CB_LIST_DETAIL_PREFIX = "show:"   # show:<account_id>

CB_STATS = "stats"

CB_EXPORT = "export"
CB_EXPORT_FMT_PREFIX = "export:"  # export:csv | export:txt

CB_ADMIN = "admin"
CB_ADMIN_ADD = "admin:add"
CB_ADMIN_REMOVE = "admin:remove"

CB_RETRY = "retry"


# ---- builders ---------------------------------------------------------------


def main_menu(*, is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("🤖 Create Account", callback_data=CB_CREATE),
            InlineKeyboardButton("📦 Bulk Create", callback_data=CB_BULK),
        ],
        [
            InlineKeyboardButton("📋 My Accounts", callback_data=f"{CB_LIST_PAGE_PREFIX}1"),
            InlineKeyboardButton("📊 Stats", callback_data=CB_STATS),
        ],
        [
            InlineKeyboardButton("📤 Export", callback_data=CB_EXPORT),
            InlineKeyboardButton("❓ Help", callback_data=CB_HELP),
        ],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("👥 Manage Users", callback_data=CB_ADMIN)])
    return InlineKeyboardMarkup(rows)


def post_create_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Create another", callback_data=CB_CREATE),
                InlineKeyboardButton("Menu", callback_data=CB_MENU),
            ]
        ]
    )


def retry_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Retry", callback_data=CB_RETRY),
                InlineKeyboardButton("Menu", callback_data=CB_MENU),
            ]
        ]
    )


def bulk_picker() -> InlineKeyboardMarkup:
    """Quick-pick bulk sizes."""
    sizes = [1, 3, 5, 10, 20]
    row = [
        InlineKeyboardButton(str(n), callback_data=f"{CB_BULK_PREFIX}{n}") for n in sizes
    ]
    return InlineKeyboardMarkup([row, [InlineKeyboardButton("Menu", callback_data=CB_MENU)]])


def list_pagination(*, page: int, total_pages: int) -> InlineKeyboardMarkup:
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("Prev", callback_data=f"{CB_LIST_PAGE_PREFIX}{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("Next", callback_data=f"{CB_LIST_PAGE_PREFIX}{page + 1}"))
    extras = [
        InlineKeyboardButton("Export", callback_data=CB_EXPORT),
        InlineKeyboardButton("Menu", callback_data=CB_MENU),
    ]
    rows = []
    if nav:
        rows.append(nav)
    rows.append(extras)
    return InlineKeyboardMarkup(rows)


def export_format_picker() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("CSV", callback_data=f"{CB_EXPORT_FMT_PREFIX}csv"),
                InlineKeyboardButton("TXT", callback_data=f"{CB_EXPORT_FMT_PREFIX}txt"),
            ],
            [InlineKeyboardButton("Menu", callback_data=CB_MENU)],
        ]
    )


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Add", callback_data=CB_ADMIN_ADD),
                InlineKeyboardButton("Remove", callback_data=CB_ADMIN_REMOVE),
            ],
            [InlineKeyboardButton("Menu", callback_data=CB_MENU)],
        ]
    )


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data=CB_MENU)]])
