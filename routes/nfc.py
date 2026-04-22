from flask import Blueprint, jsonify, request
from services.locker_service import is_locker_available, NUM_LOCKERS
from services.nfc_service import (
    nfc_process_payment, nfc_process_retrieval, nfc_get_card,
    cash_create_session, cash_insert_coin, cash_get_session
)

nfc_bp = Blueprint("nfc", __name__)


# ── Stored Value Card Payment ─────────────────────────

@nfc_bp.route("/api/nfc-scan-payment", methods=["POST"])
def api_nfc_scan_payment():
    """
    Triggered by the kiosk UI when user selects NFC payment.
    Only needs locker_number — card UID is read by the controller.
    """
    data          = request.json or {}
    locker_number = int(data.get("locker_number", 0))

    if locker_number < 1 or locker_number > NUM_LOCKERS:
        return jsonify({"ok": False, "error": "Invalid locker number."}), 400
    if not is_locker_available(locker_number):
        return jsonify({"ok": False, "error": "Locker already occupied."}), 400

    result = nfc_process_payment(locker_number)
    return jsonify(result), (200 if result.get("ok") else 400)


# ── Stored Value Card Retrieval ───────────────────────

@nfc_bp.route("/api/nfc-scan-retrieve", methods=["POST"])
def api_nfc_scan_retrieve():
    """
    Triggered by the kiosk UI when user wants to retrieve helmet.
    No body needed — card UID is read by the controller.
    """
    result = nfc_process_retrieval()
    return jsonify(result), (200 if result.get("ok") else 400)


# ── Stored Value Card Balance ─────────────────────────

@nfc_bp.route("/api/nfc-balance", methods=["POST"])
def api_nfc_balance():
    """
    Check balance of a Stored Value Card by UID.
    Hardware sends: { "card_uid": "A1B2C3D4" }
    """
    data     = request.json or {}
    card_uid = data.get("card_uid", "").strip().upper()

    if not card_uid:
        return jsonify({"ok": False, "error": "No card UID provided."}), 400

    card = nfc_get_card(card_uid)
    if not card:
        return jsonify({"ok": False, "error": "Card not registered.", "balance": 0}), 404

    return jsonify({
        "ok":                True,
        "card_uid":          card_uid,
        "balance":           card["balance"],
        "balance_display":   f"₱{card['balance'] // 100}.00",
        "has_active_rental": card.get("status") == "active",
    })


# ── Cash (Coin Acceptor) ──────────────────────────────

@nfc_bp.route("/api/cash-start", methods=["POST"])
def api_cash_start():
    """Start a coin payment session for a locker."""
    data          = request.json or {}
    locker_number = int(data.get("locker_number", 0))

    if locker_number < 1 or locker_number > NUM_LOCKERS:
        return jsonify({"ok": False, "error": "Invalid locker number."}), 400
    if not is_locker_available(locker_number):
        return jsonify({"ok": False, "error": "Locker already occupied."}), 400

    result = cash_create_session(locker_number)
    return jsonify(result), (200 if result.get("ok") else 400)


@nfc_bp.route("/api/cash-insert-coin", methods=["POST"])
def api_cash_insert_coin():
    """
    Called by coin acceptor hardware when a coin is inserted.
    Hardware sends: { "session_id": "...", "amount": 1000 }
    amount in centavos: 100=₱1, 500=₱5, 1000=₱10, 2000=₱20
    """
    data       = request.json or {}
    session_id = data.get("session_id", "").strip()
    amount     = int(data.get("amount", 0))

    if not session_id:
        return jsonify({"ok": False, "error": "No session ID provided."}), 400
    if amount <= 0:
        return jsonify({"ok": False, "error": "Invalid amount."}), 400

    result = cash_insert_coin(session_id, amount)
    return jsonify(result)


@nfc_bp.route("/api/cash-status", methods=["GET"])
def api_cash_status():
    """Polled by kiosk every 1s to check coin payment status."""
    session_id = request.args.get("session_id", "")
    if not session_id:
        return jsonify({"ok": False, "error": "No session ID."}), 400

    session = cash_get_session(session_id)
    if not session:
        return jsonify({"ok": False, "error": "Session not found."}), 404

    return jsonify({
        "ok":        True,
        "status":    session.get("status", "pending"),
        "inserted":  session.get("inserted", 0),
        "remaining": max(0, 5000 - session.get("inserted", 0)),
        "pin":       session.get("pin"),
        "locker":    session.get("locker"),
    })