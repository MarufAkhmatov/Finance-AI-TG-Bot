import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes

from db.database import (
    get_or_create_user, set_monthly_income, add_transaction,
    get_categories, get_monthly_summary, get_user_by_telegram_id,
    get_transactions, create_family, join_family, get_family_members, get_family
)
from bot.ai import chat, conversation_mgr
from bot.speech import transcribe_telegram_voice
from bot.ocr import ocr_telegram_photo
from bot.state import get_state, set_state, clear_state, State

log = logging.getLogger(__name__)

DASHBOARD_URL = "http://localhost:8900"


def _family_scope(db_user: dict) -> tuple:
    """Return (family_id, user_db_id) for DB query scoping."""
    fid = db_user.get("family_id")
    return (fid, None) if fid else (None, db_user["id"])


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user, is_new = await get_or_create_user(user.id, user.first_name)

    if is_new or db_user.get("monthly_income", 0) == 0:
        set_state(user.id, State.WAITING_INCOME_SETUP)
        await update.message.reply_text(
            f"👋 Salom, {user.first_name}!\n\n"
            "Men *FinanceAgentBot* — oilaviy moliyaviy yordamchiman 💼\n\n"
            "Xarajat va daromadlaringizni yozib boring, men tahlil qilib boraman.\n\n"
            "📊 Boshlash uchun: *Oylik daromadingiz qancha?* (so'mda yozing)\n"
            "_Masalan: 5000000_",
            parse_mode="Markdown"
        )
    else:
        now = datetime.now()
        fid, uid = _family_scope(db_user)
        income, expense = await get_monthly_summary(fid, uid, now.year, now.month)
        balance = income - expense

        family_info = ""
        if fid:
            members = await get_family_members(fid)
            names = ", ".join(m["first_name"] or "?" for m in members)
            family_info = f"👨‍👩‍👧 *Oila:* {names}\n"

        await update.message.reply_text(
            f"👋 Xush kelibsiz, {user.first_name}!\n\n"
            f"{family_info}"
            f"📅 *{now.strftime('%B %Y')} hisobi:*\n"
            f"💰 Daromad: `{income:,.0f}` so'm\n"
            f"💸 Xarajat: `{expense:,.0f}` so'm\n"
            f"📊 Balans: `{balance:,.0f}` so'm\n\n"
            "Xarajat yoki daromad yozing, ovoz yuboring yoki chek rasmini yuboring.\n"
            "👨‍👩‍👧 Oila qo'shish: /invite",
            parse_mode="Markdown"
        )


async def cmd_invite(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Generate invite command for family members."""
    user = update.effective_user
    db_user = await get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text("Avval /start ni bosing.")
        return

    # Create family if this user doesn't have one
    if not db_user.get("family_id"):
        fid = await create_family(f"{db_user['first_name'] or user.first_name} oilasi")
        await join_family(user.id, fid)
        db_user["family_id"] = fid

    fid = db_user["family_id"]
    members = await get_family_members(fid)
    member_list = "\n".join(
        f"  {'👑' if i==0 else '👤'} {m['first_name'] or '?'} (`{m['telegram_id']}`)"
        for i, m in enumerate(members)
    )

    await update.message.reply_text(
        f"👨‍👩‍👧 *Oila a'zolari ({len(members)} kishi):*\n{member_list}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"➕ *Yangi a'zo qo'shish uchun* ushbu buyruqni ulashingiz:\n\n"
        f"`/join {user.id}`\n\n"
        f"_A'zo botga kirsin va yuqoridagi buyruqni yuborsing._",
        parse_mode="Markdown"
    )


async def cmd_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Join a family by providing the family owner's telegram_id."""
    user = update.effective_user
    args = ctx.args

    if not args:
        await update.message.reply_text(
            "❌ Foydalanish: `/join <telegram_id>`\n\n"
            "_Masalan: `/join 680164608`_\n\n"
            "Oila egasi /invite bosib sizga buyruq beradi.",
            parse_mode="Markdown"
        )
        return

    try:
        target_tg_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Telegram ID raqam bo'lishi kerak.")
        return

    if target_tg_id == user.id:
        await update.message.reply_text("❌ O'zingizning ID-ingizni kiritmang.")
        return

    # Find target user
    target_user = await get_user_by_telegram_id(target_tg_id)
    if not target_user:
        await update.message.reply_text(
            f"❌ ID `{target_tg_id}` ga ega foydalanuvchi topilmadi.\n"
            "Ular avval botga /start bosishi kerak.",
            parse_mode="Markdown"
        )
        return

    # Get or create family for target
    target_family_id = target_user.get("family_id")
    if not target_family_id:
        target_family_id = await create_family(f"{target_user['first_name'] or '?'} oilasi")
        await join_family(target_tg_id, target_family_id)

    # Join current user into that family
    me = await get_user_by_telegram_id(user.id)
    if not me:
        await get_or_create_user(user.id, user.first_name)

    my_current_family = me.get("family_id") if me else None
    if my_current_family == target_family_id:
        await update.message.reply_text("✅ Siz allaqachon bu oiladasisiz!")
        return

    await join_family(user.id, target_family_id)
    members = await get_family_members(target_family_id)
    member_list = "\n".join(
        f"  {'👑' if i==0 else '👤'} {m['first_name'] or '?'}"
        for i, m in enumerate(members)
    )

    await update.message.reply_text(
        f"✅ *Oilaga qo'shildingiz!*\n\n"
        f"👨‍👩‍👧 *Oila a'zolari ({len(members)} kishi):*\n{member_list}\n\n"
        f"Endi barcha xarajat va daromadlaringiz bitta umumiy hisobda ko'rinadi.",
        parse_mode="Markdown"
    )


async def cmd_members(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await get_user_by_telegram_id(user.id)
    if not db_user or not db_user.get("family_id"):
        await update.message.reply_text(
            "Siz hali oilaga ulangansiz.\n"
            "👨‍👩‍👧 Oila yaratish: /invite\n"
            "👤 Oilaga qo'shilish: /join <id>"
        )
        return

    fid = db_user["family_id"]
    members = await get_family_members(fid)
    now = datetime.now()

    lines = []
    for i, m in enumerate(members):
        fid2, uid2 = (fid, None), m["id"]
        inc, exp = await get_monthly_summary(fid, uid2, now.year, now.month)
        # Per-member stats using user_id filter
        lines.append(
            f"{'👑' if i==0 else '👤'} *{m['first_name'] or '?'}*\n"
            f"   💸 Xarajat: `{exp:,.0f}` | 💰 Daromad: `{inc:,.0f}`"
        )

    await update.message.reply_text(
        f"👨‍👩‍👧 *Oila a'zolari — {now.strftime('%B %Y')}*\n\n"
        + "\n".join(lines) +
        f"\n\n/invite — yangi a'zo taklif qilish",
        parse_mode="Markdown"
    )


async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text("Avval /start ni bosing.")
        return

    now = datetime.now()
    fid, uid = _family_scope(db_user)
    income, expense = await get_monthly_summary(fid, uid, now.year, now.month)
    balance = income - expense
    monthly = db_user.get("monthly_income", 0)
    remaining = monthly - expense if monthly > 0 else None

    txs = await get_transactions(fid, uid, limit=5, year=now.year, month=now.month)
    last_5 = "\n".join(
        f"  {'💸' if t['type']=='expense' else '💰'} {t.get('cat_icon','')} {t['amount']:,.0f} so'm"
        f" — {t.get('cat_name') or 'Boshqa'}"
        + (f" ({t.get('member_name','')})" if fid and t.get('member_name') else "")
        for t in txs
    ) or "  Hali tranzaksiya yo'q"

    text = (
        f"📊 *{now.strftime('%B %Y')} Moliyaviy Hisobot*\n"
        f"{'─'*30}\n"
        f"💰 Daromad:  `{income:,.0f}` so'm\n"
        f"💸 Xarajat:  `{expense:,.0f}` so'm\n"
        f"📈 Balans:   `{balance:,.0f}` so'm\n"
    )
    if remaining is not None:
        pct = (expense / monthly * 100) if monthly > 0 else 0
        text += f"🎯 Byudjet:  `{monthly:,.0f}` so'm ({pct:.0f}% ishlatilgan)\n"
    text += f"\n*Oxirgi 5 ta tranzaksiya:*\n{last_5}\n\n"
    text += f"📋 Dashboard: {DASHBOARD_URL}?uid={db_user['telegram_id']}"

    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_dash(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"📊 *Dashboard* — to'liq grafiklar, kalendar va tahlil:\n\n"
        f"🌐 {DASHBOARD_URL}?uid={user.id}\n\n"
        "_Brauzerda oching_",
        parse_mode="Markdown"
    )


async def cmd_cats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    expense_cats = await get_categories("expense")
    income_cats = await get_categories("income")
    exp_list = " ".join(f"{c['icon']}{c['name']}" for c in expense_cats)
    inc_list = " ".join(f"{c['icon']}{c['name']}" for c in income_cats)
    await update.message.reply_text(
        f"📂 *Xarajat kategoriyalari:*\n{exp_list}\n\n"
        f"📂 *Daromad kategoriyalari:*\n{inc_list}",
        parse_mode="Markdown"
    )


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conversation_mgr.clear(user.id)
    clear_state(user.id)
    await update.message.reply_text("🔄 Suhbat yangilandi.")


async def _save_transaction(update: Update, db_user: dict, parsed: dict,
                            source: str = "text", receipt_file_id: str = None,
                            receipt_text: str = None):
    cats = await get_categories(parsed.get("type", "expense"))
    category_id = None
    cat_name = parsed.get("category", "Boshqa")
    for c in cats:
        if c["name"].lower() == cat_name.lower() or (c.get("name_ru") or "").lower() == cat_name.lower():
            category_id = c["id"]
            cat_name = f"{c['icon']} {c['name']}"
            break
    if category_id is None:
        category_id = cats[-1]["id"]
        cat_name = f"{cats[-1]['icon']} {cats[-1]['name']}"

    amount = float(parsed.get("amount", 0))
    ttype = parsed.get("type", "expense")
    desc = parsed.get("description", "")
    currency = parsed.get("currency", "UZS")
    family_id = db_user.get("family_id")

    tx_id = await add_transaction(
        user_db_id=db_user["id"],
        ttype=ttype,
        amount=amount,
        category_id=category_id,
        description=desc,
        source=source,
        receipt_file_id=receipt_file_id,
        receipt_text=receipt_text,
        currency=currency,
        family_id=family_id
    )

    emoji = "💸" if ttype == "expense" else "💰"
    await update.message.reply_text(
        f"✅ *Saqlandi!*\n\n"
        f"{emoji} *{cat_name}*\n"
        f"💵 `{amount:,.0f}` {currency}\n"
        f"📝 {desc or '—'}\n\n"
        f"🔢 #{tx_id} | /report — hisobot",
        parse_mode="Markdown"
    )
    return tx_id


async def _ask_for_receipt(update: Update):
    kb = ReplyKeyboardMarkup(
        [["📷 Ha, chek bor", "❌ Yo'q"]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(
        "🧾 *Chek rasmingiz bormi?*\nYuborsangiz, ma'lumotlar to'liqroq bo'ladi.",
        parse_mode="Markdown", reply_markup=kb
    )


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    s = get_state(user.id)

    if s.state == State.WAITING_INCOME_SETUP:
        digits = "".join(c for c in text if c.isdigit())
        if digits:
            amount = float(digits)
            db_user, _ = await get_or_create_user(user.id, user.first_name)
            await set_monthly_income(user.id, amount)
            clear_state(user.id)
            await update.message.reply_text(
                f"✅ Oylik daromad: *{amount:,.0f} so'm* saqlandi!\n\n"
                "Endi xarajat yoki daromadingizni yozing. Masalan:\n"
                "_\"Tushlik 25000\"_ yoki _\"Metro 1400\"_\n\n"
                "👨‍👩‍👧 Oila a'zolarini qo'shish: /invite",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await update.message.reply_text(
                "Iltimos, raqam kiriting. Masalan: _5000000_", parse_mode="Markdown"
            )
        return

    if s.state == State.WAITING_RECEIPT:
        if "ha" in text.lower() or "📷" in text:
            set_state(user.id, State.WAITING_RECEIPT)
            await update.message.reply_text(
                "📷 Chek rasmini yuboring:", reply_markup=ReplyKeyboardRemove()
            )
        else:
            db_user = await get_user_by_telegram_id(user.id)
            await _save_transaction(update, db_user, s.pending_transaction,
                                    source=s.pending_message or "text")
            clear_state(user.id)
        return

    db_user, _ = await get_or_create_user(user.id, user.first_name)
    await update.message.reply_text("⏳ Tahlil qilyapman...")
    display, parsed = chat(user.id, text)

    if parsed and parsed.get("amount", 0) > 0:
        set_state(user.id, State.WAITING_RECEIPT, transaction=parsed, message=text)
        if display:
            await update.message.reply_text(display)
        await _ask_for_receipt(update)
    else:
        await update.message.reply_text(display or "Javob yo'q.", reply_markup=ReplyKeyboardRemove())


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text("🎤 Ovoz qabul qilindi, matnga aylantiryapman...")

    text = await transcribe_telegram_voice(ctx.bot, update.message.voice.file_id)
    if not text:
        await update.message.reply_text("❌ Ovozni tushuna olmadim. Qayta urinib ko'ring.")
        return

    await update.message.reply_text(f"🎙 *Siz dedingiz:* _{text}_", parse_mode="Markdown")
    db_user, _ = await get_or_create_user(user.id, user.first_name)
    display, parsed = chat(user.id, text)

    if parsed and parsed.get("amount", 0) > 0:
        set_state(user.id, State.WAITING_RECEIPT, transaction=parsed, message=text)
        if display:
            await update.message.reply_text(display)
        await _ask_for_receipt(update)
    else:
        await update.message.reply_text(display or "Tahlil qilib bo'lmadi.")


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    s = get_state(user.id)

    photo = update.message.photo[-1]
    await update.message.reply_text("📷 Chek skanlanmoqda...", reply_markup=ReplyKeyboardRemove())
    receipt_text = await ocr_telegram_photo(ctx.bot, photo.file_id)

    if s.state == State.WAITING_RECEIPT and s.pending_transaction:
        db_user = await get_user_by_telegram_id(user.id)
        parsed = s.pending_transaction.copy()
        if receipt_text:
            await update.message.reply_text(
                f"📄 *Chekdan o'qildi:*\n`{receipt_text[:300]}`", parse_mode="Markdown"
            )
            _, reparsed = chat(
                user.id, f"Chekdan ma'lumot: {receipt_text[:500]}\nIlgari aytilgan: {s.pending_message or ''}"
            )
            if reparsed and reparsed.get("amount", 0) > 0:
                parsed = reparsed
        await _save_transaction(update, db_user, parsed, source="receipt",
                                receipt_file_id=photo.file_id, receipt_text=receipt_text)
        clear_state(user.id)
    else:
        db_user, _ = await get_or_create_user(user.id, user.first_name)
        if receipt_text:
            await update.message.reply_text(
                f"📄 *Chekdan o'qildi:*\n`{receipt_text[:300]}`", parse_mode="Markdown"
            )
            display, parsed = chat(user.id, f"Bu chekdagi xarajat: {receipt_text[:500]}")
            if parsed and parsed.get("amount", 0) > 0:
                await _save_transaction(update, db_user, parsed, source="receipt",
                                        receipt_file_id=photo.file_id, receipt_text=receipt_text)
            else:
                await update.message.reply_text(display or "Chekdan miqdorni aniqlay olmadim. Qo'lda yozing.")
        else:
            await update.message.reply_text(
                "❌ Chekdan matn o'qib bo'lmadi. Qo'lda yozing:\n_Masalan: Magnit 45000_",
                parse_mode="Markdown"
            )
