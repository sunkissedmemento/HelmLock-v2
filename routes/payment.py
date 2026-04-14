import os
import stripe
from flask import Blueprint, jsonify, render_template, request
from services.locker_service import (
    is_locker_available, create_rental, check_pin,
    unlock_locker, mark_overtime_paid, generate_pin,
    calc_overtime, now_utc, NUM_LOCKERS, RENTAL_PRICE
)
from services.stripe_service import (
    is_stripe_configured, create_rental_session, create_overtime_session
)
from services.db import db_get_transaction_by_pin

payment_bp = Blueprint("payment", __name__)

# ── In-memory session store ───────────────────────────
# Stores pending and completed session data while kiosk is polling.
# { session_id: { "status": "pending"|"paid", "pin": ..., "locker": ..., ... } }
_session_store: dict = {}


# ── Pages ────────────────────────────────────────────

@payment_bp.route("/")
def index():
    return render_template("index.html")

@payment_bp.route("/payment-cancelled")
def payment_cancelled():
    return render_template("payment_cancelled.html")


# ── Rental Payment ───────────────────────────────────

@payment_bp.route("/api/create-stripe-session", methods=["POST"])
def api_create_stripe_session():
    """
    Validates locker availability then creates a Stripe Checkout session.
    Returns both the URL (for QR) and session_id (for polling).
    In dev mode, immediately saves transaction and returns PIN.
    """
    data          = request.json or {}
    locker_number = int(data.get("locker_number", 0))

    if locker_number < 1 or locker_number > NUM_LOCKERS:
        return jsonify({"error": "Invalid locker number."}), 400

    if not is_locker_available(locker_number):
        return jsonify({"error": "Locker already occupied."}), 400

    # Dev mode — no Stripe key present
    if not is_stripe_configured():
        pin                   = generate_pin()
        rented_at, expires_at = create_rental(locker_number, "stripe_dev", RENTAL_PRICE, pin)
        return jsonify({
            "dev_mode":   True,
            "pin":        pin,
            "locker":     locker_number,
            "rented_at":  rented_at.strftime("%b %d, %Y %I:%M %p"),
            "expires_at": expires_at.strftime("%I:%M %p"),
        })

    try:
        url, session_id = create_rental_session(locker_number)
        # Register session as pending so kiosk can poll
        _session_store[session_id] = {"status": "pending", "locker": locker_number}
        return jsonify({"url": url, "session_id": session_id})
    except Exception as e:
        print(f"[Stripe] create_rental_session error: {e}")
        return jsonify({"error": str(e)}), 500


@payment_bp.route("/payment-success")
def payment_success():
    """
    Stripe redirects here on the USER'S PHONE after payment.
    Shows a simple confirmation — the kiosk updates via webhook/polling.
    """
    locker_number = request.args.get("locker", "?")
    return render_template("payment_success.html", locker=locker_number)


# ── Stripe Webhook ───────────────────────────────────

@payment_bp.route("/api/stripe-webhook", methods=["POST"])
def stripe_webhook():
    """
    Receives Stripe events. On checkout.session.completed:
    - Generates PIN
    - Saves transaction to Supabase
    - Marks locker occupied
    - Updates _session_store so kiosk polling picks it up
    """
    payload    = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except stripe.error.SignatureVerificationError:
        print("[Webhook] Signature verification failed")
        return jsonify({"error": "Invalid signature"}), 400
    except Exception as e:
        print(f"[Webhook] Error: {e}")
        return jsonify({"error": str(e)}), 400

    if event["type"] == "checkout.session.completed":
        session       = event["data"]["object"]
        session_id    = session["id"]
        locker_number = int(session.get("metadata", {}).get("locker_number", 0))

        if locker_number:
            pin = generate_pin()
            rented_at, expires_at = create_rental(locker_number, "stripe", RENTAL_PRICE, pin)

            # Update session store so kiosk polling returns "paid"
            _session_store[session_id] = {
                "status":     "paid",
                "pin":        pin,
                "locker":     locker_number,
                "rented_at":  rented_at.strftime("%b %d, %Y %I:%M %p"),
                "expires_at": expires_at.strftime("%b %d, %Y %I:%M %p"),
            }
            print(f"[Webhook] Payment confirmed — Locker #{locker_number} | PIN={pin}")

    return jsonify({"received": True}), 200


# ── Session Status Polling ───────────────────────────

@payment_bp.route("/api/session-status")
def api_session_status():
    """
    Polled by kiosk every 3 seconds while QR screen is shown.
    Checks Stripe directly for payment status.
    """
    session_id = request.args.get("session_id", "")
    if not session_id:
        return jsonify({"status": "unknown"}), 400

    # Check in-memory store first (set by webhook if it fires)
    stored = _session_store.get(session_id, {})
    if stored.get("status") == "paid":
        return jsonify(stored)

    # Fall back to polling Stripe directly
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == "paid":
            locker_number = int(session.metadata.get("locker_number", 0))
            if locker_number:
                # Check if we already created a rental for this session
                if session_id not in _session_store or _session_store[session_id].get("status") != "paid":
                    pin = generate_pin()
                    rented_at, expires_at = create_rental(locker_number, "stripe", RENTAL_PRICE, pin)
                    _session_store[session_id] = {
                        "status":     "paid",
                        "pin":        pin,
                        "locker":     locker_number,
                        "rented_at":  rented_at.strftime("%b %d, %Y %I:%M %p"),
                        "expires_at": expires_at.strftime("%b %d, %Y %I:%M %p"),
                    }
                    print(f"[Polling] Payment confirmed — Locker #{locker_number} | PIN={pin}")
                return jsonify(_session_store[session_id])
        return jsonify({"status": "pending"})
    except Exception as e:
        print(f"[Polling] Stripe error: {e}")
        return jsonify({"status": "pending"})

# ── PIN & Unlock ─────────────────────────────────────

@payment_bp.route("/api/check-pin", methods=["POST"])
def api_check_pin():
    """
    Validates PIN and returns status without unlocking.
    Frontend uses this to decide: unlock immediately or show overtime screen.
    """
    pin = (request.json or {}).get("pin", "").strip()

    if not pin.isdigit() or len(pin) != 6:
        return jsonify({"ok": False, "message": "Invalid PIN format."})

    result = check_pin(pin)
    return jsonify(result)


@payment_bp.route("/api/unlock", methods=["POST"])
def api_unlock():
    """
    Unlocks the locker if PIN is valid and overtime (if any) is paid.
    Marks transaction as retrieved and frees locker in DB.
    """
    pin = (request.json or {}).get("pin", "").strip()

    if not pin.isdigit() or len(pin) != 6:
        return jsonify({"ok": False, "message": "Invalid PIN format."})

    result = unlock_locker(pin)
    return jsonify(result)


# ── Overtime Payment ─────────────────────────────────

@payment_bp.route("/api/create-overtime-session", methods=["POST"])
def api_create_overtime_session():
    """
    Creates a Stripe Checkout session for overtime charges.
    Overtime amount is recalculated server-side.
    """
    data = request.json or {}
    pin  = data.get("pin", "").strip()

    if not pin.isdigit() or len(pin) != 6:
        return jsonify({"error": "Invalid PIN."}), 400

    row = db_get_transaction_by_pin(pin)
    if not row:
        return jsonify({"error": "Transaction not found."}), 404

    is_ot, ot_hours, ot_amount = calc_overtime(row["expires_at"])
    if not is_ot:
        return jsonify({"error": "No overtime detected."}), 400

    locker_number = row["locker_number"]

    if not is_stripe_configured():
        mark_overtime_paid(pin, ot_amount)
        return jsonify({"dev_mode": True, "pin": pin, "locker": locker_number})

    try:
        url = create_overtime_session(locker_number, pin, ot_hours, ot_amount)
        return jsonify({"url": url})
    except Exception as e:
        print(f"[Stripe] create_overtime_session error: {e}")
        return jsonify({"error": str(e)}), 500


@payment_bp.route("/overtime-success")
def overtime_success():
    """
    Stripe redirects here after overtime payment.
    Marks overtime as paid — user can now enter PIN to unlock.
    """
    pin           = request.args.get("pin", "")
    locker_number = request.args.get("locker", "?")

    if pin:
        row = db_get_transaction_by_pin(pin)
        if row:
            _, _, ot_amount = calc_overtime(row["expires_at"])
            mark_overtime_paid(pin, ot_amount)

    return render_template("overtime_paid.html", locker=locker_number, pin=pin)