import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "finance.db")

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    first_name TEXT,
    monthly_income REAL DEFAULT 0,
    currency TEXT DEFAULT 'UZS',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_ru TEXT,
    icon TEXT DEFAULT '💰',
    type TEXT DEFAULT 'expense'
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'UZS',
    category_id INTEGER,
    description TEXT,
    receipt_file_id TEXT,
    receipt_text TEXT,
    source TEXT DEFAULT 'text',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);
"""

DEFAULT_CATEGORIES = [
    ("Oziq-ovqat",   "Еда",          "🍔", "expense"),
    ("Transport",    "Транспорт",    "🚗", "expense"),
    ("Kiyim",        "Одежда",       "👔", "expense"),
    ("Sog'liq",      "Здоровье",     "💊", "expense"),
    ("Ta'lim",       "Образование",  "📚", "expense"),
    ("Ko'ngilochar", "Развлечения",  "🎮", "expense"),
    ("Kommunal",     "Коммунальные", "⚡", "expense"),
    ("Uy-joy",       "Жильё",        "🏠", "expense"),
    ("Boshqa",       "Другое",       "❓", "expense"),
    ("Maosh",        "Зарплата",     "💰", "income"),
    ("Biznes",       "Бизнес",       "💼", "income"),
    ("Freelance",    "Фриланс",      "💻", "income"),
    ("Daromad-boshqa", "Доход-другое", "📥", "income"),
]

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        for stmt in CREATE_SQL.strip().split(";"):
            s = stmt.strip()
            if s:
                await db.execute(s)
        # Insert default categories if empty
        cur = await db.execute("SELECT COUNT(*) FROM categories")
        count = (await cur.fetchone())[0]
        if count == 0:
            await db.executemany(
                "INSERT INTO categories (name, name_ru, icon, type) VALUES (?,?,?,?)",
                DEFAULT_CATEGORIES
            )
        await db.commit()

async def get_or_create_user(telegram_id: int, first_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        row = await cur.fetchone()
        if row:
            return dict(row), False
        await db.execute(
            "INSERT INTO users (telegram_id, first_name) VALUES (?,?)",
            (telegram_id, first_name)
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        row = await cur.fetchone()
        return dict(row), True

async def set_monthly_income(telegram_id: int, amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET monthly_income=? WHERE telegram_id=?",
            (amount, telegram_id)
        )
        await db.commit()

async def add_transaction(user_db_id: int, ttype: str, amount: float,
                          category_id: int, description: str,
                          source: str = "text", receipt_file_id: str = None,
                          receipt_text: str = None, currency: str = "UZS"):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO transactions
               (user_id, type, amount, currency, category_id, description, source, receipt_file_id, receipt_text)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (user_db_id, ttype, amount, currency, category_id, description, source, receipt_file_id, receipt_text)
        )
        await db.commit()
        return cur.lastrowid

async def get_categories(ttype: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if ttype:
            cur = await db.execute("SELECT * FROM categories WHERE type=?", (ttype,))
        else:
            cur = await db.execute("SELECT * FROM categories")
        return [dict(r) for r in await cur.fetchall()]

async def get_category_by_name(name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM categories WHERE LOWER(name)=LOWER(?) OR LOWER(name_ru)=LOWER(?)",
            (name, name)
        )
        return await cur.fetchone()

async def get_monthly_summary(user_db_id: int, year: int, month: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT type, SUM(amount) as total
            FROM transactions
            WHERE user_id=?
              AND strftime('%Y', created_at)=?
              AND strftime('%m', created_at)=?
            GROUP BY type
        """, (user_db_id, str(year), f"{month:02d}"))
        rows = {r["type"]: r["total"] for r in await cur.fetchall()}
        return rows.get("income", 0), rows.get("expense", 0)

async def get_transactions(user_db_id: int, limit: int = 50, offset: int = 0,
                           year: int = None, month: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        filters = "WHERE t.user_id=?"
        params = [user_db_id]
        if year:
            filters += " AND strftime('%Y', t.created_at)=?"
            params.append(str(year))
        if month:
            filters += " AND strftime('%m', t.created_at)=?"
            params.append(f"{month:02d}")
        cur = await db.execute(f"""
            SELECT t.*, c.name as cat_name, c.icon as cat_icon
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            {filters}
            ORDER BY t.created_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])
        return [dict(r) for r in await cur.fetchall()]

async def get_category_stats(user_db_id: int, year: int, month: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT c.name, c.icon, SUM(t.amount) as total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.user_id=? AND t.type='expense'
              AND strftime('%Y', t.created_at)=?
              AND strftime('%m', t.created_at)=?
            GROUP BY t.category_id
            ORDER BY total DESC
        """, (user_db_id, str(year), f"{month:02d}"))
        return [dict(r) for r in await cur.fetchall()]

async def get_calendar_data(user_db_id: int, year: int, month: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT strftime('%d', created_at) as day,
                   type, SUM(amount) as total
            FROM transactions
            WHERE user_id=?
              AND strftime('%Y', created_at)=?
              AND strftime('%m', created_at)=?
            GROUP BY day, type
        """, (user_db_id, str(year), f"{month:02d}"))
        return [dict(r) for r in await cur.fetchall()]

async def get_trend_data(user_db_id: int, months: int = 6):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT strftime('%Y-%m', created_at) as month,
                   type, SUM(amount) as total
            FROM transactions
            WHERE user_id=?
              AND created_at >= date('now', ? || ' months')
            GROUP BY month, type
            ORDER BY month
        """, (user_db_id, f"-{months}"))
        return [dict(r) for r in await cur.fetchall()]

async def get_user_by_telegram_id(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        row = await cur.fetchone()
        return dict(row) if row else None
