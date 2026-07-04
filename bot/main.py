import os
import logging
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from bot.handlers import (
    cmd_start, cmd_report, cmd_dash, cmd_cats, cmd_reset,
    cmd_invite, cmd_join, cmd_members,
    handle_text, handle_voice, handle_photo
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set. Check your .env file.")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


def build_app():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("report",  cmd_report))
    app.add_handler(CommandHandler("dash",    cmd_dash))
    app.add_handler(CommandHandler("cats",    cmd_cats))
    app.add_handler(CommandHandler("reset",   cmd_reset))
    app.add_handler(CommandHandler("invite",  cmd_invite))
    app.add_handler(CommandHandler("join",    cmd_join))
    app.add_handler(CommandHandler("members", cmd_members))

    app.add_handler(MessageHandler(filters.VOICE,        handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO,        handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app
