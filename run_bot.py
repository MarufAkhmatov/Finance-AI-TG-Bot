"""
FinanceAgentBot — Finance Manager
Bot + Dashboard + Cloudflare Tunnel (no warning page)
"""
import asyncio
import logging
import threading
import subprocess
import sys
import os
import re
import time

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

BASE_DIR = os.path.dirname(__file__)

# cloudflared binary — env var > local .exe > system PATH
CF_BIN = os.environ.get("CF_BIN") or os.path.join(BASE_DIR, "cloudflared.exe")
if not os.path.exists(CF_BIN):
    CF_BIN = "cloudflared"


def run_dashboard():
    import uvicorn
    uvicorn.run(
        "dashboard.api:app",
        host="0.0.0.0",
        port=8900,
        log_level="warning",
        reload=False
    )


def start_cloudflare_tunnel() -> tuple:
    """Start cloudflared quick tunnel for port 8900. Returns (url, proc)."""
    proc = subprocess.Popen(
        [CF_BIN, "tunnel", "--url", "http://localhost:8900",
         "--no-autoupdate", "--metrics", "localhost:9090"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    # Read output until we find the trycloudflare.com URL
    url = None
    for _ in range(60):
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.3)
            continue
        m = re.search(r'https://[a-z0-9\-]+\.trycloudflare\.com', line)
        if m:
            url = m.group(0)
            break
        if proc.poll() is not None:
            break
    # Drain remaining startup output in background
    def _drain():
        for _ in proc.stdout:
            pass
    threading.Thread(target=_drain, daemon=True).start()
    return url, proc


async def set_menu_button(bot, url: str):
    from telegram import MenuButtonWebApp, WebAppInfo
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="📊 Dashboard",
                web_app=WebAppInfo(url=url)
            )
        )
        log.info("Menu button → %s", url)
    except Exception as e:
        log.warning("Menu button error: %s", e)


async def run_bot(tunnel_url: str = None):
    from db.database import init_db
    from bot.main import build_app

    await init_db()
    app = build_app()
    await app.initialize()
    await app.start()

    if tunnel_url:
        await set_menu_button(app.bot, tunnel_url)

    await app.updater.start_polling(drop_pending_updates=True)
    log.info("🤖 Bot running | Dashboard: %s", tunnel_url or "no tunnel")

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

    # 1. Dashboard
    threading.Thread(target=run_dashboard, daemon=True).start()
    log.info("Dashboard → http://localhost:8900")
    time.sleep(2)

    # 2. Cloudflare tunnel
    log.info("Starting Cloudflare tunnel...")
    tunnel_url, cf_proc = start_cloudflare_tunnel()
    if tunnel_url:
        log.info("✅ Tunnel: %s", tunnel_url)
    else:
        log.warning("⚠️  Tunnel failed — dashboard won't open in Telegram")
        cf_proc = None

    # 3. Bot
    try:
        asyncio.run(run_bot(tunnel_url))
    finally:
        if cf_proc:
            cf_proc.terminate()
