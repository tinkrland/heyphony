"""telegram: a bot api webhook, signed by a header instead of a body hmac.

telegram is the easiest lane here and that is worth saying plainly rather than treating as a
suspicious shortcut: one https endpoint, one header it echoes back, no dashboard archaeology, no
unofficial bridge. the cost is that a bot is a bot, who it may speak to is a whitelist, and a group
chat is a room rather than a person, so it is never whitelisted.
"""
import hmac
import json
import os

LANE = {
    "name": "telegram", "folder": "telegram",
    "carrier": "telegram bot api (http webhook)",
    "intake": "secret-token header -> one envelope",
    "relay": "sendmessage, one chat at a time",
    "gate": ("TELEGRAM_BOT_TOKEN", "TELEGRAM_WEBHOOK_SECRET"),
    "state": "designed",
    "evidence": "the header gate and the group refusal are tested; no bot has been created yet",
}


def _header(headers, name):
    for key, value in (headers or {}).items():
        if key.lower() == name:
            return value
    return ""


def verify(headers, env=None):
    """telegram sets the header we told it to set at setwebhook time. compare, do not parse."""
    env = env if env is not None else os.environ
    secret = env.get("TELEGRAM_WEBHOOK_SECRET", "")
    if not secret:
        return False, "TELEGRAM_WEBHOOK_SECRET unset: the lane is closed, not open"
    got = _header(headers, "x-telegram-bot-api-secret-token")
    if not got:
        return False, "missing x-telegram-bot-api-secret-token"
    if not hmac.compare_digest(got, secret):
        return False, "bad secret token"
    return True, "ok"


def allowed_chats(env=None):
    env = env if env is not None else os.environ
    raw = env.get("TELEGRAM_ALLOWED_CHATS", "")
    return {c.strip() for c in raw.split(",") if c.strip()}


def normalize(update):
    """one update -> the umbrella's envelope, or a refusal with its reason."""
    msg = (update or {}).get("message") or (update or {}).get("edited_message") or {}
    if not msg:
        return {"ok": False, "why": "no message in this update (callbacks and receipts are intake too, just not yet)"}
    chat = msg.get("chat") or {}
    kind = chat.get("type", "")
    if kind in ("group", "supergroup", "channel"):
        return {"ok": False, "why": "group-reply", "detail": "a group chat is a room, not somebody asking"}
    who = msg.get("from") or {}
    sender = who.get("username") or str(who.get("id", ""))
    text = msg.get("text") or msg.get("caption") or ""
    return {"ok": True, "envelope": {
        "id": f"telegram:{update.get('update_id')}",
        "channel": "telegram",
        "direction": "in",
        "sender": sender,
        "recipient": "bot",
        "subject": "",
        "body": text,
        "at": msg.get("date"),
        "thread": str(chat.get("id", "")),
        "reply_to": "",
        "raw": update,
    }}


def handle(raw_body, headers, env=None):
    """401 for a bad signature, 403 for a stranger, 200 for a person who asked."""
    env = env if env is not None else os.environ
    ok, why = verify(headers, env)
    if not ok:
        return {"status": 401, "body": {"error": why}}
    try:
        update = json.loads(raw_body or "{}")
    except json.JSONDecodeError:
        return {"status": 400, "body": {"error": "not json"}}
    shaped = normalize(update)
    if not shaped["ok"]:
        return {"status": 403, "body": {"error": shaped["why"], "detail": shaped.get("detail", "")}}
    chat_id = shaped["envelope"]["thread"]
    if chat_id not in allowed_chats(env):
        return {"status": 403, "body": {"error": "chat not whitelisted", "chat": chat_id}}
    return {"status": 200, "body": {"ok": True, "envelope": shaped["envelope"]}}


def reply_plan(chat_id, text, env=None):
    env = env if env is not None else os.environ
    if not env.get("TELEGRAM_BOT_TOKEN"):
        return {"sendable": False, "why": "TELEGRAM_BOT_TOKEN unset"}
    return {"sendable": True, "chat_id": chat_id, "text": text, "method": "sendMessage"}
