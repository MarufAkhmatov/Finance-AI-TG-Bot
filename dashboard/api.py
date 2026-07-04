from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime
import os

from db.database import (
    get_monthly_summary, get_transactions, get_category_stats,
    get_calendar_data, get_trend_data, get_user_by_telegram_id,
    get_categories, get_family_members, get_member_stats
)

app = FastAPI(title="ZakatBot Finance Dashboard")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def _scope(user: dict) -> tuple:
    fid = user.get("family_id")
    return (fid, None) if fid else (None, user["id"])


@app.get("/api/user")
async def api_user(uid: int = Query(...)):
    user = await get_user_by_telegram_id(uid)
    if not user:
        return {"error": "User not found"}
    result = {
        "id":           user["id"],
        "name":         user["first_name"],
        "monthly_income": user["monthly_income"],
        "currency":     user["currency"],
        "family_id":    user.get("family_id"),
        "is_family":    bool(user.get("family_id")),
    }
    if user.get("family_id"):
        members = await get_family_members(user["family_id"])
        result["family_members"] = [
            {"name": m["first_name"], "telegram_id": m["telegram_id"]}
            for m in members
        ]
    return result


@app.get("/api/summary")
async def api_summary(uid: int = Query(...), year: int = None, month: int = None):
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    user = await get_user_by_telegram_id(uid)
    if not user:
        return {"error": "User not found"}
    fid, u_id = _scope(user)
    income, expense = await get_monthly_summary(fid, u_id, year, month)
    budget = user["monthly_income"]
    return {
        "year": year, "month": month,
        "income": income, "expense": expense,
        "balance": income - expense,
        "monthly_budget": budget,
        "budget_used_pct": round(expense / budget * 100, 1) if budget > 0 else 0,
        "family_id": fid,
    }


@app.get("/api/transactions")
async def api_transactions(uid: int = Query(...), limit: int = 50,
                           offset: int = 0, year: int = None, month: int = None):
    user = await get_user_by_telegram_id(uid)
    if not user:
        return []
    fid, u_id = _scope(user)
    return await get_transactions(fid, u_id, limit=limit, offset=offset, year=year, month=month)


@app.get("/api/categories/stats")
async def api_cat_stats(uid: int = Query(...), year: int = None, month: int = None):
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    user = await get_user_by_telegram_id(uid)
    if not user:
        return []
    fid, u_id = _scope(user)
    return await get_category_stats(fid, u_id, year, month)


@app.get("/api/calendar")
async def api_calendar(uid: int = Query(...), year: int = None, month: int = None):
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    user = await get_user_by_telegram_id(uid)
    if not user:
        return []
    fid, u_id = _scope(user)
    return await get_calendar_data(fid, u_id, year, month)


@app.get("/api/trends")
async def api_trends(uid: int = Query(...), months: int = 6):
    user = await get_user_by_telegram_id(uid)
    if not user:
        return []
    fid, u_id = _scope(user)
    return await get_trend_data(fid, u_id, months)


@app.get("/api/members")
async def api_members(uid: int = Query(...), year: int = None, month: int = None):
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    user = await get_user_by_telegram_id(uid)
    if not user or not user.get("family_id"):
        return []
    return await get_member_stats(user["family_id"], year, month)


@app.get("/api/categories")
async def api_categories():
    return await get_categories()


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
