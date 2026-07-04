from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime
import os

from db.database import (
    get_monthly_summary, get_transactions, get_category_stats,
    get_calendar_data, get_trend_data, get_user_by_telegram_id,
    get_categories
)

app = FastAPI(title="ZakatBot Finance Dashboard")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@app.get("/api/user")
async def api_user(uid: int = Query(...)):
    user = await get_user_by_telegram_id(uid)
    if not user:
        return {"error": "User not found"}
    return {
        "id": user["id"],
        "name": user["first_name"],
        "monthly_income": user["monthly_income"],
        "currency": user["currency"],
    }


@app.get("/api/summary")
async def api_summary(uid: int = Query(...), year: int = None, month: int = None):
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    user = await get_user_by_telegram_id(uid)
    if not user:
        return {"error": "User not found"}
    income, expense = await get_monthly_summary(user["id"], year, month)
    return {
        "year": year,
        "month": month,
        "income": income,
        "expense": expense,
        "balance": income - expense,
        "monthly_budget": user["monthly_income"],
        "budget_used_pct": round(expense / user["monthly_income"] * 100, 1) if user["monthly_income"] > 0 else 0
    }


@app.get("/api/transactions")
async def api_transactions(uid: int = Query(...), limit: int = 50,
                           offset: int = 0, year: int = None, month: int = None):
    user = await get_user_by_telegram_id(uid)
    if not user:
        return []
    return await get_transactions(user["id"], limit=limit, offset=offset, year=year, month=month)


@app.get("/api/categories/stats")
async def api_cat_stats(uid: int = Query(...), year: int = None, month: int = None):
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    user = await get_user_by_telegram_id(uid)
    if not user:
        return []
    return await get_category_stats(user["id"], year, month)


@app.get("/api/calendar")
async def api_calendar(uid: int = Query(...), year: int = None, month: int = None):
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    user = await get_user_by_telegram_id(uid)
    if not user:
        return []
    return await get_calendar_data(user["id"], year, month)


@app.get("/api/trends")
async def api_trends(uid: int = Query(...), months: int = 6):
    user = await get_user_by_telegram_id(uid)
    if not user:
        return []
    return await get_trend_data(user["id"], months)


@app.get("/api/categories")
async def api_categories():
    return await get_categories()


# Serve static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
