import math
import random
import string
from datetime import datetime, timezone, timedelta

from services.db import (
    db_get_all_lockers,
    db_get_locker_status,
    db_set_locker,
    db_get_overdue_transactions,
    db_update_transaction,
    db_get_transaction_by_pin,
)

# ── Hardware Controller ───────────────────────────────
try:
    from controller.controller import store as ctrl_store, claim as ctrl_claim
    _HW = True
except Exception as e:
    print(f"[Service] Controller unavailable ({e}); hardware disabled.")
    _HW = False


# ── Config ─────────────────────────────────────────────
NUM_LOCKERS   = 12
SESSION_HOURS = 1
RENTAL_PRICE  = 5000  # centavos (₱50)

_dev_store = {}


# ── Time Utilities ────────────────────────────────────

def now_utc():
    return datetime.now(timezone.utc)


def parse_dt(s):
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)

    s = str(s).replace(" ", "T", 1)
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def format_time_left(expires_at):
    diff = parse_dt(expires_at) - now_utc()
    secs = int(diff.total_seconds())

    if secs <= 0:
        return "Expired"

    h, rem = divmod(secs, 3600)
    m = rem // 60

    if h:
        return f"{h} hr {m} min remaining"
    return f"{m} min remaining"


def calc_overtime(expires_at):
    diff = now_utc() - parse_dt(expires_at)
    secs = int(diff.total_seconds())

    if secs <= 0:
        return False, 0, 0

    hours_over = math.ceil(secs / 3600)
    amount_due = hours_over * RENTAL_PRICE

    return True, hours_over, amount_due


def generate_pin(length=6):
    return ''.join(random.choices(string.digits, k=length))


# ── Locker Status ─────────────────────────────────────

def get_all_locker_statuses():
    db_map = db_get_all_lockers()

    if db_map:
        return [
            {"number": i, "status": db_map.get(i, "available")}
            for i in range(1, NUM_LOCKERS + 1)
        ]

    occupied = {v["locker_number"] for v in _dev_store.values() if v["status"] == "active"}

    return [
        {
            "number": i,
            "status": "occupied" if i in occupied else "available"
        }
        for i in range(1, NUM_LOCKERS + 1)
    ]


def is_locker_available(locker_number: int) -> bool:
    status = db_get_locker_status(locker_number)
    return status == "available"


# ── Rental Creation ───────────────────────────────────

def create_rental(locker_number: int, payment_method: str, amount: int, pin: str):
    locker_number = int(locker_number)
    rented_at = now_utc()
    expires_at = rented_at + timedelta(hours=SESSION_HOURS)

    from services.db import db_insert_transaction

    ok = db_insert_transaction({
        "locker_number": locker_number,
        "payment_method": payment_method,
        "amount": amount,
        "pin": pin,
        "status": "active",
        "rented_at": rented_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "retrieved_at": None,
        "overtime_paid": False,
        "overtime_amount": 0,
    })

    if ok:
        db_set_locker(locker_number, "occupied")

        print(f"[Service] Rental created — Locker #{locker_number} PIN={pin}")

        # ONLY command Arduino to store
        if _HW:
            try:
                ctrl_store(locker_number)
            except Exception as e:
                print(f"[HW] Store error (non-fatal): {e}")

    else:
        print(f"[Service] ERROR: failed to create rental")

    if not db_get_all_lockers():
        _dev_store[pin] = {
            "locker_number": locker_number,
            "payment_method": payment_method,
            "amount": amount,
            "status": "active",
            "rented_at": rented_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "overtime_paid": False,
            "overtime_amount": 0,
        }

    return rented_at, expires_at


# ── PIN Check ─────────────────────────────────────────

def check_pin(pin: str):
    row = db_get_transaction_by_pin(pin)

    if not row:
        if pin in _dev_store:
            row = _dev_store[pin]
        else:
            return {"ok": False, "message": "Invalid PIN"}

    is_ot, ot_hours, ot_amount = calc_overtime(row["expires_at"])

    return {
        "ok": True,
        "locker": row["locker_number"],
        "time_left": format_time_left(row["expires_at"]) if not is_ot else "Expired",
        "is_overtime": is_ot,
        "overtime_paid": row.get("overtime_paid", False),
        "overtime_hours": ot_hours,
        "overtime_amount": ot_amount,
        "overtime_amount_display": f"₱{ot_amount // 100}.00",
    }


# ── Claim Locker ──────────────────────────────────────

def claim_locker(pin: str):
    row = db_get_transaction_by_pin(pin)

    if not row:
        if pin in _dev_store:
            row = _dev_store[pin]
        else:
            return {"ok": False, "message": "Invalid PIN"}

    is_ot, _, _ = calc_overtime(row["expires_at"])

    if is_ot and not row.get("overtime_paid", False):
        return {"ok": False, "message": "Overtime not paid"}

    db_update_transaction(row["id"], {
        "status": "retrieved",
        "retrieved_at": now_utc().isoformat(),
    })

    db_set_locker(row["locker_number"], "available")

    if pin in _dev_store:
        _dev_store[pin]["status"] = "retrieved"

    print(f"[Service] Locker #{row['locker_number']} claimed PIN={pin}")

    # ONLY claim command (no sanitise here)
    if _HW:
        try:
            ctrl_claim(row["locker_number"])
        except Exception as e:
            print(f"[HW] Claim error (non-fatal): {e}")

    return {"ok": True, "locker": row["locker_number"]}


# ── Overtime Payment ──────────────────────────────────

def mark_overtime_paid(pin: str, amount: int):
    row = db_get_transaction_by_pin(pin)

    if not row:
        if pin in _dev_store:
            _dev_store[pin]["overtime_paid"] = True
            _dev_store[pin]["overtime_amount"] = amount
            return {"ok": True}
        return {"ok": False}

    _, _, ot_amount = calc_overtime(row["expires_at"])

    db_update_transaction(row["id"], {
        "overtime_paid": True,
        "overtime_amount": ot_amount,
    })

    print(f"[Service] Overtime paid Locker #{row['locker_number']} ₱{ot_amount // 100}.00")

    return {"ok": True, "locker": row["locker_number"]}