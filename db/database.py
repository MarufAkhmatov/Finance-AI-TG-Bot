import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "finance.db")

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS families (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT DEFAULT 'Oila',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    first_name TEXT,
    monthly_income REAL DEFAULT 0,
    currency TEXT DEFAULT 'UZS',
    family_id INTEGER REFERENCES families(id),
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
    family_id INTEGER,
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
    FOREIGN KEY (family_id) REFERENCES families(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);
"""

DEFAULT_CATEGORIES = [
    ("Oziq-ovqat",     "Еда",          "🍔", "expense"),
    ("Transport",      "Транспорт",    "🚗", "expense"),
    ("Kiyim",          "Одежда",       "👔", "expense"),
    ("Sog'liq",        "Здоровье",     "💊", "expense"),
    ("Ta'lim",         "Образование",  "📚", "expense"),
    ("Ko'ngilochar",   "Развлечения",  "🎮", "expense"),
    ("Kommunal",       "Коммунальные", "⚡", "expense"),
    ("Uy-joy",         "Жильё",        "🏠", "expense"),
    ("Boshqa",         "Другое",       "❓", "expense"),
    ("Maosh",          "Зарплата",     "💰", "income"),
    ("Biznes",         "Бизнес",       "💼", "income"),
    ("Freelance",      "Фриланс",      "💻", "income"),
    ("Daromad-boshqa", "Доход-другое", "📥", "income"),
]


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        for stmt in CREATE_SQL.strip().split(";"):
            s = stmt.strip()
            if s:
                await db.execute(s)
        # Migrate: add family_id to users if missing
        try:
            await db.execute("ALTER TABLE users ADD COLUMN family_id INTEGER REFERENCES families(id)")
        except Exception:
            pass
        # Migrate: add family_id to transactions if missing
        try:
            await db.execute("ALTER TABLE transactions ADD COLUMN family_id INTEGER REFERENCES families(id)")
        except Exception:
            pass
        cur = await db.execute("SELECT COUNT(*) FROM categories")
        if (await cur.fetchone())[0] == 0:
            await db.executemany(
                "INSERT INTO categories (name, name_ru, icon, type) VALUES (?,?,?,?)",
                DEFAULT_CATEGORIES
            )
        await db.commit()


# ── Family ────────────────────────────────────────────────────────

async def create_family(name: str = "Oila") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("INSERT INTO families (name) VALUES (?)", (name,))
        await db.commit()
        return cur.lastrowid


async def get_family(family_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM families WHERE id=?", (family_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_family_members(family_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM users WHERE family_id=? ORDER BY created_at", (family_id,)
        )
        return [dict(r) for r in await cur.fetchall()]


async def join_family(telegram_id: int, family_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET family_id=? WHERE telegram_id=?", (family_id, telegram_id)
        )
        # Back-fill existing transactions
        cur = await db.execute("SELECT id FROM users WHERE telegram_id=?", (telegram_id,))
        row = await cur.fetchone()
        if row:
            await db.execute(
                "UPDATE transactions SET family_id=? WHERE user_id=? AND family_id IS NULL",
                (family_id, row[0])
            )
        await db.commit()


# ── User ───────────────────────────────────────────────────────��──

async def get_or_create_user(telegram_id: int, first_name: str) -> tuple[dict, bool]:
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
        return dict(await cur.fetchone()), True


async def get_user_by_telegram_id(telegram_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_monthly_income(telegram_id: int, amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET monthly_income=? WHERE telegram_id=?", (amount, telegram_id)
        )
        await db.commit()


# ── Transactions ─────────────────────────────────────────────────

async def add_transaction(user_db_id: int, ttype: str, amount: float,
                          category_id: int, description: str,
                          source: str = "text", receipt_file_id: str = None,
                          receipt_text: str = None, currency: str = "UZS",
                          family_id: int = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO transactions
               (user_id, family_id, type, amount, currency, category_id,
                description, source, receipt_file_id, receipt_text)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (user_db_id, family_id, ttype, amount, currency, category_id,
             description, source, receipt_file_id, receipt_text)
        )
        await db.commit()
        return cur.lastrowid


async def get_categories(ttype: str = None) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if ttype:
            cur = await db.execute("SELECT * FROM categories WHERE type=?", (ttype,))
        else:
            cur = await db.execute("SELECT * FROM categories")
        return [dict(r) for r in await cur.fetchall()]


def _scope_filter(family_id: int | None, user_db_id: int | None) -> tuple[str, list]:
    """Return WHERE clause and params to scope by family or user."""
    if family_id:
        return "t.family_id=?", [family_id]
    return "t.user_id=?", [user_db_id]


async def get_monthly_summary(family_id: int | None, user_db_id: int | None,
                               year: int, month: int) -> tuple[float, float]:
    where, params = _scope_filter(family_id, user_db_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(f"""
            SELECT type, SUM(amount) as total FROM transactions t
            WHERE {where}
              AND strftime('%Y', created_at)=?
              AND strftime('%m', created_at)=?
            GROUP BY type
        """, params + [str(year), f"{month:02d}"])
        rows = {r["type"]: r["total"] for r in await cur.fetchall()}
        return rows.get("income", 0), rows.get("expense", 0)


async def get_transactions(family_id: int | None, user_db_id: int | None,
                           limit: int = 50, offset: int = 0,
                           year: int = None, month: int = None) -> list:
    where, params = _scope_filter(family_id, user_db_id)
    if year:
        where += " AND strftime('%Y', t.created_at)=?"
        params.append(str(year))
    if month:
        where += " AND strftime('%m', t.created_at)=?"
        params.append(f"{month:02d}")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(f"""
            SELECT t.*, c.name as cat_name, c.icon as cat_icon,
                   u.first_name as member_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id=c.id
            LEFT JOIN users u ON t.user_id=u.id
            WHERE {where}
            ORDER BY t.created_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])
        return [dict(r) for r in await cur.fetchall()]


async def get_category_stats(family_id: int | None, user_db_id: int | None,
                             year: int, month: int) -> list:
    where, params = _scope_filter(family_id, user_db_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(f"""
            SELECT c.name, c.icon, SUM(t.amount) as total
            FROM transactions t JOIN categories c ON t.category_id=c.id
            WHERE {where} AND t.type='expense'
              AND strftime('%Y', t.created_at)=?
              AND strftime('%m', t.created_at)=?
            GROUP BY t.category_id ORDER BY total DESC
        """, params + [str(year), f"{month:02d}"])
        return [dict(r) for r in await cur.fetchall()]


async def get_calendar_data(family_id: int | None, user_db_id: int | None,
                            year: int, month: int) -> list:
    where, params = _scope_filter(family_id, user_db_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(f"""
            SELECT strftime('%d', created_at) as day, type, SUM(amount) as total
            FROM transactions t
            WHERE {where}
              AND strftime('%Y', created_at)=?
              AND strftime('%m', created_at)=?
            GROUP BY day, type
        """, params + [str(year), f"{month:02d}"])
        return [dict(r) for r in await cur.fetchall()]


async def get_trend_data(family_id: int | None, user_db_id: int | None,
                         months: int = 6) -> list:
    where, params = _scope_filter(family_id, user_db_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(f"""
            SELECT strftime('%Y-%m', created_at) as month, type, SUM(amount) as total
            FROM transactions t
            WHERE {where} AND created_at >= date('now', ? || ' months')
            GROUP BY month, type ORDER BY month
        """, params + [f"-{months}"])
        return [dict(r) for r in await cur.fetchall()]


async def get_member_stats(family_id: int, year: int, month: int) -> list:
    """Per-member spending breakdown for the family."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT u.first_name, u.telegram_id,
                   SUM(CASE WHEN t.type='expense' THEN t.amount ELSE 0 END) as expense,
                   SUM(CASE WHEN t.type='income'  THEN t.amount ELSE 0 END) as income
            FROM transactions t JOIN users u ON t.user_id=u.id
            WHERE t.family_id=?
              AND strftime('%Y', t.created_at)=?
              AND strftime('%m', t.created_at)=?
            GROUP BY t.user_id
        """, (family_id, str(year), f"{month:02d}"))
        return [dict(r) for r in await cur.fetchall()]
