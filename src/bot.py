"""Telegram bot wiring: builds the Application, registers handlers, manages lifecycle."""
from __future__ import annotations

import sys

from loguru import logger
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from .config import Settings, load_settings
from .elevenlabs import ElevenLabsSignup
from .kameleo import KameleoBackend
from .handlers import admin as h_admin
from .handlers import bulk as h_bulk
from .handlers import create as h_create
from .handlers import export as h_export
from .handlers import list as h_list
from .handlers import stats as h_stats
from .handlers import start as h_start
from .menu import (
    CB_ADMIN,
    CB_ADMIN_ADD,
    CB_ADMIN_REMOVE,
    CB_BULK,
    CB_BULK_PREFIX,
    CB_CREATE,
    CB_EXPORT,
    CB_EXPORT_FMT_PREFIX,
    CB_HELP,
    CB_LIST_DETAIL_PREFIX,
    CB_LIST_PAGE_PREFIX,
    CB_MENU,
    CB_RETRY,
    CB_STATS,
)

# ✅ تغییر: به جای PinMX از Guerrilla استفاده می‌کنیم
from .guerrilla import GuerrillaMailClient  # <-- خط جدید
from .supabase_client import Repo


# ---- lifecycle hooks --------------------------------------------------------


async def _post_init(app: Application) -> None:
    settings: Settings = app.bot_data["settings"]
    repo: Repo = app.bot_data["repo"]

    repo.bootstrap_admin(settings.admin_telegram_id)
    logger.info("Bootstrap admin {} ensured", settings.admin_telegram_id)

    # ✅ استفاده از Guerrilla به جای PinMX
    guerrilla = GuerrillaMailClient()
    try:
        await guerrilla.self_check()
        logger.info("✅ Guerrilla Mail self-check OK (free tier active)")
    except Exception as exc:
        logger.error("❌ Guerrilla Mail self-check failed: {}", exc)
        # چون Guerrilla نیازی به بستن ندارد، فقط raise می‌کنیم
        raise

    kameleo: KameleoBackend | None = None
    if settings.browser_mode == "kameleo":
        kameleo = KameleoBackend(
            base_url=settings.kameleo_base_url,
            device_type=settings.kameleo_device_type,
            browser_product=settings.kameleo_browser_product,
            os_family=settings.kameleo_os_family,
        )
        try:
            await kameleo.self_check()
            logger.info("Kameleo self-check OK at {}", settings.kameleo_base_url)
        except Exception as exc:
            logger.error("Kameleo self-check failed: {}", exc)
            raise
    elif settings.browser_mode == "playwright":
        logger.info("Using plain Playwright Chromium (no anti-detect)")
    else:
        raise RuntimeError(
            f"BROWSER_MODE must be 'kameleo' or 'playwright', got {settings.browser_mode!r}"
        )

    elevenlabs = ElevenLabsSignup(
        headless=settings.headless,
        signup_url=settings.elevenlabs_signup_url,
        kameleo=kameleo,
    )
    await elevenlabs.__aenter__()

    # ✅ ذخیره guerrilla به جای pinmx
    app.bot_data["guerrilla"] = guerrilla
    app.bot_data["elevenlabs"] = elevenlabs
    app.bot_data["kameleo"] = kameleo

    logger.info("Bot started, admin bootstrapped — ready to accept messages")


async def _post_shutdown(app: Application) -> None:
    # ✅ Guerrilla نیازی به بستن ندارد، فقط ElevenLabs را می‌بندیم
    elevenlabs: ElevenLabsSignup | None = app.bot_data.get("elevenlabs")
    if elevenlabs is not None:
        await elevenlabs.__aexit__(None, None, None)
    logger.info("Bot shut down cleanly")


# ---- handler registration ---------------------------------------------------


def _register_handlers(app: Application) -> None:
    # Slash commands
    app.add_handler(CommandHandler("start", h_start.cmd_start))
    app.add_handler(CommandHandler("menu", h_start.cmd_menu))
    app.add_handler(CommandHandler("help", h_start.cmd_help))

    app.add_handler(CommandHandler("create", h_create.cmd_create))
    app.add_handler(CommandHandler("bulk", h_bulk.cmd_bulk))
    app.add_handler(CommandHandler("list", h_list.cmd_list))
    app.add_handler(CommandHandler("stats", h_stats.cmd_stats))
    app.add_handler(CommandHandler("export", h_export.cmd_export))

    app.add_handler(CommandHandler("add_user", h_admin.cmd_add_user))
    app.add_handler(CommandHandler("remove_user", h_admin.cmd_remove_user))
    app.add_handler(CommandHandler("list_users", h_admin.cmd_list_users))

    # Callback queries (inline buttons). Order matters — match prefixes first.
    app.add_handler(CallbackQueryHandler(h_start.cb_menu, pattern=f"^{CB_MENU}$"))
    app.add_handler(CallbackQueryHandler(h_start.cb_help, pattern=f"^{CB_HELP}$"))
    app.add_handler(CallbackQueryHandler(h_create.cb_create, pattern=f"^{CB_CREATE}$"))
    app.add_handler(CallbackQueryHandler(h_create.cb_create, pattern=f"^{CB_RETRY}$"))
    app.add_handler(CallbackQueryHandler(h_bulk.cb_bulk_menu, pattern=f"^{CB_BULK}$"))
    app.add_handler(CallbackQueryHandler(h_bulk.cb_bulk_pick, pattern=f"^{CB_BULK_PREFIX}\\d+$"))
    app.add_handler(CallbackQueryHandler(h_list.cb_list, pattern=f"^{CB_LIST_PAGE_PREFIX}\\d+$"))
    app.add_handler(
        CallbackQueryHandler(h_list.cb_show, pattern=f"^{CB_LIST_DETAIL_PREFIX}.+$")
    )
    app.add_handler(CallbackQueryHandler(h_stats.cb_stats, pattern=f"^{CB_STATS}$"))
    app.add_handler(CallbackQueryHandler(h_export.cb_export_menu, pattern=f"^{CB_EXPORT}$"))
    app.add_handler(
        CallbackQueryHandler(
            h_export.cb_export_format, pattern=f"^{CB_EXPORT_FMT_PREFIX}(csv|txt)$"
        )
    )
    app.add_handler(CallbackQueryHandler(h_admin.cb_admin, pattern=f"^{CB_ADMIN}$"))
    app.add_handler(CallbackQueryHandler(h_admin.cb_admin_add, pattern=f"^{CB_ADMIN_ADD}$"))
    app.add_handler(
        CallbackQueryHandler(h_admin.cb_admin_remove, pattern=f"^{CB_ADMIN_REMOVE}$")
    )

    # Plain-text catcher for admin add/remove follow-up messages.
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin.text_admin_action)
    )


# ---- entrypoint -------------------------------------------------------------


def _configure_logging(level: str) -> None:
    logger.remove()
    logger.add(sys.stderr, level=level, enqueue=False, backtrace=False, diagnose=False)


def build_application(settings: Settings) -> Application:
    repo = Repo(settings.supabase_url, settings.supabase_service_key)
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .concurrent_updates(True)
        .build()
    )
    app.bot_data["settings"] = settings
    app.bot_data["repo"] = repo
    _register_handlers(app)
    return app


def run() -> None:
    settings = load_settings()
    _configure_logging(settings.log_level)
    logger.info("Loading settings — admin={}", settings.admin_telegram_id)
    app = build_application(settings)
    app.run_polling()
