"""
ZakatBot — Finance Manager
Botni ham, dashboardni ham bir vaqtda ishga tushiradi.
"""
import asyncio
import logging
import threading
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

# Load .env
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

log = logging.getLogger(__name__)


def run_dashboard():
    import uvicorn
    uvicorn.run(
        "dashboard.api:app",
        host="127.0.0.1",
        port=8900,
        log_level="warning",
        reload=False
    )


async def run_bot():
    from db.database import init_db
    from bot.main import build_app

    await init_db()
    log.info("Database initialized")

    app = build_app()
    log.info("Bot starting — @my_n8n_for_ai_bot")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("Bot is running. Ctrl+C to stop.")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # Dashboard background thread
    t = threading.Thread(target=run_dashboard, daemon=True)
    t.start()
    log.info("Dashboard started at http://127.0.0.1:8900")

    # Bot (main thread)
    asyncio.run(run_bot())
