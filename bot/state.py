"""
Har user uchun conversation state machine
"""
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class State(Enum):
    IDLE = "idle"
    WAITING_INCOME_SETUP = "waiting_income_setup"
    CONFIRM_ENTRY = "confirm_entry"
    WAITING_RECEIPT = "waiting_receipt"
    WAITING_CATEGORY = "waiting_category"


@dataclass
class UserState:
    state: State = State.IDLE
    pending_transaction: Optional[dict] = None  # parsed transaction data
    pending_message: Optional[str] = None       # original user message


_states: dict[int, UserState] = {}


def get_state(user_id: int) -> UserState:
    if user_id not in _states:
        _states[user_id] = UserState()
    return _states[user_id]


def set_state(user_id: int, state: State, transaction: dict = None, message: str = None):
    s = get_state(user_id)
    s.state = state
    if transaction is not None:
        s.pending_transaction = transaction
    if message is not None:
        s.pending_message = message


def clear_state(user_id: int):
    _states[user_id] = UserState()
