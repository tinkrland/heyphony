"""signal: the lane that gets cheap once a number exists.

signal has no bot api. the honest shape is signal-cli (unofficial) or its rest
wrapper, linked as a secondary device, and the number question answered by heyphony
rather than by this module.
"""
import os

LANE = {
    "name": "signal", "folder": "signal",
    "carrier": "signal-cli or signal-cli-rest-api",
    "intake": "the linked device's own message stream",
    "relay": "same device, same cli",
    "gate": ("SIGNAL_CLI_URL",),
    "state": "designed",
    "evidence": "the three paths are named and the number dependency is explicit; no device has been linked",
    "bootstrap": "heyphony get signal",
}

PATHS = {
    "phone-signup": {
        "needs": ["a durable but idle android spawnable", "the did, whose sms heyphony catches"],
        "needs_number_of_its_own": True,
        "command": "heyphony get signal --path phone-signup",
        "note": "the phone is the identity of record and does not have to stay awake; the code is read from heyphony's inbox on the desktop, which is the trick in one sentence",
    },
    "link-desktop": {
        "needs": ["a phone that already owns the account", "a qr scan, a human act"],
        "needs_number_of_its_own": False,
        "command": "heyphony get signal --path link-desktop",
        "note": "one identity, two devices: the phone stays primary, the agent's desktop is the secondary device a laptop would be",
    },
    "register-number": {
        "needs": ["a number whose sms we can receive", "a captcha if signal asks for one"],
        "needs_number_of_its_own": True,
        "command": "heyphony get signal --path register-number",
        "note": "no device of record behind it, so it is the weakest of the three even though signal is far less strict about voip than whatsapp or google",
    },
}

REFUSALS = {
    "bot-api": "signal has no bot or app api. a lane that claims one is lying",
    "bulk": "signal treats automation-heavy accounts as spam, so this lane is for people who talk to the agent",
}


def registration_plan(path="phone-signup", env=None):
    env = env if env is not None else os.environ
    if path not in PATHS:
        return {"possible": False, "why": f"not a signal path: {path}"}
    spec = PATHS[path]
    have_number = bool(env.get("HEYPHONY_SIP_DID"))
    missing = []
    if spec["needs_number_of_its_own"] and not have_number:
        missing.append("HEYPHONY_SIP_DID (the number whose sms we receive)")
    return {"path": path, "possible": not missing, "missing": missing, "steps": spec["needs"],
            "one_command": "heyphony get signal",
            "needs_number_of_its_own": spec["needs_number_of_its_own"], "command": spec["command"],
            "note": spec["note"], "refusals": REFUSALS}
