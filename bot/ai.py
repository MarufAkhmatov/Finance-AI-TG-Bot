"""
Finance Manager AI — Claude CLI orqali (port 3099)
Har user uchun conversation history saqlanadi.
"""
import json
import re
import requests
import logging
from typing import Optional

log = logging.getLogger(__name__)

import os
CLAUDE_URL = os.environ.get("CLAUDE_URL", "http://127.0.0.1:3099/chat")

SYSTEM_PROMPT = """Sen FinanceAgentBot — professional shaxsiy moliyaviy maslahatchi va Finance Managersen.

VAZIFANG:
- Foydalanuvchi xarajat yoki daromad haqida yozganda miqdor va kategoriyani aniqla
- O'zbek yoki rus tilida javob ber (foydalanuvchi qaysi tilda yozsa, shunda)
- Qisqa, professional va do'stona bo'l
- Faqat moliyaviy maslahatlar ber

KATEGORIYALAR (expense): Oziq-ovqat, Transport, Kiyim, Sog'liq, Ta'lim, Ko'ngilochar, Kommunal, Uy-joy, Boshqa
KATEGORIYALAR (income): Maosh, Biznes, Freelance, Daromad-boshqa

MUHIM: Hech qachon IT loyihalari, dasturlash, Claude Code, yoki boshqa texnik mavzular haqida gapirma.

Agar foydalanuvchi xarajat/daromad yozsa, javobingni DOIM quyidagi formatda yakunla:
[PARSED]{"type":"expense","amount":0,"currency":"UZS","category":"Boshqa","description":""}[/PARSED]

Agar xarajat/daromad emas (suhbat, savol, maslahat so'rasa) — [PARSED] blokini qo'shma."""


class ConversationManager:
    def __init__(self, max_turns: int = 20):
        self.histories: dict[int, list] = {}
        self.max_turns = max_turns

    def get_history(self, user_id: int) -> list:
        return self.histories.get(user_id, [])

    def add_turn(self, user_id: int, role: str, content: str):
        if user_id not in self.histories:
            self.histories[user_id] = []
        self.histories[user_id].append({"role": role, "content": content})
        # Keep max_turns * 2 messages (user + assistant pairs)
        if len(self.histories[user_id]) > self.max_turns * 2:
            self.histories[user_id] = self.histories[user_id][-self.max_turns * 2:]

    def clear(self, user_id: int):
        self.histories[user_id] = []

    def build_prompt(self, user_id: int, new_message: str) -> str:
        history = self.get_history(user_id)
        parts = [SYSTEM_PROMPT, ""]
        for turn in history:
            role = "Foydalanuvchi" if turn["role"] == "user" else "FinanceAgentBot"
            parts.append(f"{role}: {turn['content']}")
        parts.append(f"Foydalanuvchi: {new_message}")
        parts.append("FinanceAgentBot:")
        return "\n".join(parts)


conversation_mgr = ConversationManager()


def ask_claude_raw(prompt: str) -> str:
    try:
        r = requests.post(CLAUDE_URL, json={"prompt": prompt}, timeout=120)
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception as e:
        log.error("Claude error: %s", e)
        return ""


def chat(user_id: int, message: str) -> tuple[str, Optional[dict]]:
    """
    Returns (display_text, parsed_transaction_or_None)
    """
    prompt = conversation_mgr.build_prompt(user_id, message)
    raw = ask_claude_raw(prompt)

    if not raw:
        return "Kechirasiz, xato yuz berdi. Qayta urinib ko'ring.", None

    # Extract parsed transaction if present
    parsed = None
    display = raw

    match = re.search(r'\[PARSED\](.*?)\[/PARSED\]', raw, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1).strip())
            # Remove [PARSED] block from display text
            display = raw[:match.start()].strip()
            if not display:
                display = _format_confirmation(parsed)
        except json.JSONDecodeError:
            pass

    # Save to history (without the PARSED block)
    conversation_mgr.add_turn(user_id, "user", message)
    conversation_mgr.add_turn(user_id, "assistant", display)

    return display, parsed


def _format_confirmation(parsed: dict) -> str:
    ttype = "💰 Daromad" if parsed.get("type") == "income" else "💸 Xarajat"
    amount = parsed.get("amount", 0)
    currency = parsed.get("currency", "UZS")
    category = parsed.get("category", "Boshqa")
    desc = parsed.get("description", "")
    return f"{ttype} qo'shildi: {amount:,.0f} {currency} — {category}" + (f" ({desc})" if desc else "")


def ask_finance_question(user_id: int, question: str) -> str:
    """For non-transaction financial questions."""
    prompt = conversation_mgr.build_prompt(user_id, question)
    return ask_claude_raw(prompt) or "Kechirasiz, xato. Qayta urinib ko'ring."
