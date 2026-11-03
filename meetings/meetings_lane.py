"""meetings: join a room, hear it, be heard, share the screen.

the zoom signature is ported from clawtel (meetings/platforms/zoom/signature.ts) and
the livekit/screenshare shapes from prixie's voice branch. nothing here records and
publishes on its own.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

PLATFORMS = {
    "zoom": {"join": "web sdk in the spawnable browser, signed token",
             "gate": ("ZOOM_SDK_KEY", "ZOOM_SDK_SECRET"), "state": "designed",
             "signal": "raise hand, reactions, screenshare"},
    "meet": {"join": "the room's own web client, no token",
             "gate": (), "state": "designed",
             "signal": "browser ui only, no host api"},
    "teams": {"join": "web client, tenant permission needed for the app",
              "gate": ("MS_TENANT_ID",), "state": "designed",
              "signal": "browser ui only"},
}

RAILS = {
    "audio": {"how": "livekit room the meeting already has: join as a participant, publish tts, subscribe for stt",
              "why": "no new person requests into the call; the agent is a mouth on the connection it holds",
              "gate": ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"), "state": "designed"},
    "screenshare": {"how": "getdisplaymedia from inside the spawnable (headed chrome under xvfb, https)",
                    "why": "the browser shares its own screen; nothing is re-streamed through us",
                    "gate": (), "state": "verified in a spawnable, unverified in a real meeting"},
}

LANE = {
    "name": "meetings", "folder": "meetings",
    "carrier": "a browser in a spawnable, plus livekit for audio",
    "intake": "the room: speech, chat, transcript",
    "relay": "speech and a shared screen, never a recording posted anywhere",
    "gate": ("ZOOM_SDK_KEY", "ZOOM_SDK_SECRET"),
    "state": "designed",
    "evidence": "zoom signing round-trip tested here; no real meeting has been joined from this branch",
}


def _b64(text):
    return base64.b64encode(text.encode()).decode()


def lane_available(env=None):
    env = env if env is not None else os.environ
    return bool(env.get("ZOOM_SDK_KEY") and env.get("ZOOM_SDK_SECRET"))


def sign_zoom_join(meeting_number, role=0, valid_for=7200, now=None, env=None):
    env = env if env is not None else os.environ
    key, secret = env.get("ZOOM_SDK_KEY"), env.get("ZOOM_SDK_SECRET")
    if not key or not secret:
        raise RuntimeError("zoom lane is closed: ZOOM_SDK_KEY / ZOOM_SDK_SECRET are unset")
    iat = int(now or time.time()) - 30
    exp = iat + valid_for
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    payload = _b64(json.dumps({"sdkKey": key, "mn": str(meeting_number), "role": role,
                               "iat": iat, "exp": exp, "tokenExp": exp}, separators=(",", ":")))
    message = f"{header}.{payload}"
    signature = _b64(hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest())
    return {"sdk_key": key, "meeting_number": str(meeting_number), "role": role,
            "signature": signature, "join_token": _b64(f"{signature}.{message}.{secrets.token_hex(10)}"),
            "iat": iat, "exp": exp}


def verify_zoom_token(token, env=None):
    env = env if env is not None else os.environ
    secret = env.get("ZOOM_SDK_SECRET")
    if not secret:
        return False
    try:
        parts = base64.b64decode(token).decode().split(".")
    except (ValueError, UnicodeDecodeError):
        return False
    if len(parts) != 4:
        return False
    expected = _b64(hmac.new(secret.encode(), f"{parts[1]}.{parts[2]}".encode(), hashlib.sha256).hexdigest())
    return hmac.compare_digest(expected, parts[0])


def join_plan(platform, meeting_number, env=None):
    env = env if env is not None else os.environ
    if platform not in PLATFORMS:
        return {"joinable": False, "why": f"platform not modelled: {platform}"}
    spec = PLATFORMS[platform]
    missing = [g for g in spec["gate"] if not env.get(g)]
    plan = {"platform": platform, "meeting": str(meeting_number), "join": spec["join"],
            "signal": spec["signal"], "state": spec["state"], "joinable": not missing,
            "missing": missing, "rails": RAILS,
            "scope": "the browser joins as a participant. it renders and hands back, it never publishes."}
    if platform == "zoom" and not missing:
        plan["token"] = sign_zoom_join(meeting_number, env=env)
    return plan
