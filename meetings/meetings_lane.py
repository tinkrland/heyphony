"""meetings: join a room, hear it, be heard, share the screen.

the data is `rails.py`, one folder up, because the page, the signature notes and this lane all have
to read from one place. what lives here is the part that is code: minting and checking zoom's join
token, and building the plan a given platform's join actually needs.

the zoom signature is ported from clawtel (meetings/platforms/zoom/signature.ts) and the audio rails
from prixie's voice branch. nothing here records and nothing publishes: it renders, and it hands back.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import rails  # noqa: E402

# the lane in the shape the registry and the page both read: the carrier, the intake, the relay, the
# gate and the state, with the evidence for that state rather than a claim without one.
LANE = {
    "name": "meetings",
    "folder": "meetings",
    "carrier": "a browser in a spawnable, plus livekit for the audio",
    "intake": "the room: speech, chat, transcript",
    "relay": "speech and a shared screen, never a recording posted anywhere",
    "gate": ("ZOOM_SDK_KEY", "ZOOM_SDK_SECRET"),
    "state": "designed",
    "evidence": "the zoom join token is minted and re-verified in tests/selftest.py; "
                "no real meeting has been joined from this branch",
}

PLATFORMS = {
    name: {
        "join": row["join"],
        "gate": tuple(row["gate"]),
        "state": row["state"],
        "signal": row["signal"],
        "audio": row["audio"],
        "screenshare": row["screenshare"],
    }
    for name, row in rails.RAILS.items()
}

RAILS = {
    "audio": {
        "how": "livekit room the meeting already has: join as a participant, publish tts, subscribe for stt",
        "why": "no new person is requested into the call; the agent is a mouth on the connection it holds",
        "gate": ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"),
        "state": "designed",
    },
    "screenshare": {
        "how": "getdisplaymedia from inside the browser that joined",
        "why": "the browser shares its own screen; nothing is re-streamed through us",
        "gate": (),
        "state": "designed in a real meeting, verified in a spawnable",
    },
}


def _b64(text):
    return base64.b64encode(text.encode()).decode()


def lane_available(env=None):
    """a lane with an unset secret is closed, which is the one rule every lane here inherits."""
    env = env if env is not None else os.environ
    return bool(env.get("ZOOM_SDK_KEY") and env.get("ZOOM_SDK_SECRET"))


def sign_zoom_join(meeting_number, role=0, valid_for=7200, now=None, env=None):
    """the meeting sdk join token: an hs256 header and payload, a signature over both, a random tail."""
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
            "signature": signature,
            "join_token": _b64(f"{signature}.{message}.{secrets.token_hex(10)}"),
            "iat": iat, "exp": exp}


def verify_zoom_token(token, env=None):
    """recompute over the two parts the carrier will recompute over, and compare in constant time."""
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
    expected = _b64(hmac.new(secret.encode(), f"{parts[1]}.{parts[2]}".encode(),
                             hashlib.sha256).hexdigest())
    return hmac.compare_digest(expected, parts[0])


def join_plan(platform, meeting_number, env=None):
    """what joining this room takes, and which part of it is missing today. deterministic, no io."""
    env = env if env is not None else os.environ
    if platform not in PLATFORMS:
        return {"joinable": False, "modelled": False,
                "why": f"platform not modelled: {platform}",
                "known": sorted(PLATFORMS)}
    spec = PLATFORMS[platform]
    missing = [gate for gate in spec["gate"] if not env.get(gate)]
    plan = {"platform": platform, "meeting": str(meeting_number), "modelled": True,
            "join": spec["join"], "signal": spec["signal"], "state": spec["state"],
            "audio": spec["audio"], "screenshare": spec["screenshare"],
            "joinable": not missing, "missing": missing, "rails": RAILS,
            "scope": "the browser joins as a participant. it renders and hands back, it never publishes."}
    if platform == "zoom" and not missing:
        plan["token"] = sign_zoom_join(meeting_number, env=env)
    return plan
