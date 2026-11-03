"""slack: the events api, signed with the same v0 scheme as imessage."""
import os

from comms import gates

LANE = {
    "name": "slack", "folder": "slack",
    "carrier": "slack events api (http webhook)",
    "intake": "signed event -> one envelope",
    "relay": "chat.postMessage with a bot token",
    "gate": ("SLACK_SIGNING_SECRET",),
    "state": "designed",
    "evidence": "the v0 gate is tested; the app has never been installed",
}


def verify(raw_body, headers, env=None):
    env = env if env is not None else os.environ
    return gates.slack(raw_body, headers, env.get("SLACK_SIGNING_SECRET", ""))


def handle(raw_body, headers, env=None):
    """slack retries anything it does not get a 200 for, so the url check is answered first."""
    env = env if env is not None else os.environ
    ok, why = verify(raw_body, headers, env)
    if not ok:
        return {"status": 401, "body": {"error": why}}
    if '"type":"url_verification"' in raw_body.replace(" ", ""):
        import json, re
        challenge = re.search(r'"challenge"\s*:\s*"([^"]*)"', raw_body)
        return {"status": 200, "body": {"challenge": challenge.group(1) if challenge else ""}}
    return {"status": 200, "body": {"ok": True}}


def reply_plan(channel, text, env=None):
    env = env if env is not None else os.environ
    if not env.get("SLACK_BOT_TOKEN"):
        return {"sendable": False, "why": "SLACK_BOT_TOKEN unset"}
    return {"sendable": True, "channel": channel, "text": text, "method": "chat.postMessage"}
