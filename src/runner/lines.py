"""the state of this host as a person reads it: one line per capability, a mark, and why.

`heyphony status` answers a script, and that is the right shape for a script. "is my number working" is
a different question with a different answer: a mark, the thing it is about, and the shortest reason that
is still true. so this is a second rendering of the same facts rather than a second set of facts.

four marks, because three would lie. green is proof: something here can only be green because a message
arrived or a file exists. orange is configured-but-unproven, which is the state most of this repo is
actually in. red is nothing there. and dim is not-known-yet: nothing has been tried, so calling it broken
would be as wrong as calling it fine.
"""

import os
import sys

from src.linphone import sip
from src.manage import allow, inbox, views
from src.setup import routes

MARKS = {
    "ok": ("\u2713", "32"),       # green
    "partial": ("!", "33"),       # orange
    "missing": ("\u2717", "31"),  # red
    "unknown": ("\u00b7", "2"),   # dim
}

ORDER = {"missing": 0, "partial": 1, "unknown": 2, "ok": 3}


def colour_on(stream=None, flag=None, environ=None):
    """colour when a person is watching, never when a pipe is. an explicit flag wins over the guess."""
    environ = os.environ if environ is None else environ
    if environ.get("NO_COLOR"):
        return False
    if environ.get("FORCE_COLOR"):
        return True
    if flag is not None:
        return bool(flag)
    stream = stream or sys.stdout
    return bool(getattr(stream, "isatty", lambda: False)())


def paint(mark, state, on=True):
    symbol, code = MARKS[state]
    return "\x1b[{}m{}\x1b[0m".format(code, symbol) if on else symbol


def checks(policy=None, message_count=None, voicemail_count=None, env=None):
    """every line, in the order a person debugs in: the number, then the rails, then the gates."""
    env = os.environ if env is None else env
    rc = sip.rc_path()
    did = _did()
    rows = []

    rows.append(_line("number", "ok" if did else ("partial" if rc.is_file() else "missing"),
                      did or ("a config exists at {} with no did in it".format(rc) if rc.is_file()
                              else "no did yet: `heyphony setup links` opens the portal that sells one"),
                      fix=None if did else "heyphony connect sip --voipms --did +1..."))

    style = sip.host_client()
    rows.append(_line("sip client", "ok" if style.get("client") else "unknown",
                      "{} on this host".format(style.get("client")) if style.get("client")
                      else "which client the host runs is not decided yet"))

    count = inbox.count() if message_count is None else message_count
    route = routes.ROUTES.get(_provider() or "", None)
    if route is None:
        rows.append(_line("texts inbound", "unknown", "no provider chosen, so no route to arm",
                          fix="heyphony setup select sip"))
    else:
        hook = routes.hook(_provider())
        http = route["kind"] in ("webhook-json", "url-forward", "post-to-url")
        rows.append(_line("texts inbound", "ok" if count else "partial",
                          "{} route, and {} message{} have arrived through it".format(
                              route["kind"], count, "" if count == 1 else "s") if count
                          else "{} route is designed: {} is not proof".format(
                              route["kind"], "the url" if http else "the mailbox"),
                          fix=None if count else "heyphony hooks {} --template".format(_provider()),
                          detail=hook["paste_url"] or "email relay"))

    last = _last_message()
    rows.append(_line("a text has arrived", "ok" if count else "missing",
                      "{} stored{}".format(count, ", the newest " + _ago(last) if last else "")
                      if count else "nothing has ever arrived, so every inbound line above is a plan",
                      fix=None if count else "one real message from a phone settles it"))

    policy = policy if policy is not None else allow.load()
    mode = policy.get("mode")
    listed = len(policy.get("allow_numbers") or [])
    if mode in ("open", None):
        rows.append(_line("who may reach you", "partial",
                          "mode {}: every sender is heard".format(mode or "unset"),
                          fix="heyphony allow mode local"))
    elif listed == 0:
        rows.append(_line("who may reach you", "missing",
                          "mode {} with an empty list, so nothing can reach this number".format(mode),
                          fix="heyphony allow allow +1... for the people who should get through"))
    else:
        rows.append(_line("who may reach you", "ok",
                          "mode {}, {} number{} on the list".format(mode, listed,
                                                                   "" if listed == 1 else "s")))

    gate = env.get("HEYPHONY_SEND") == "allowed"
    rows.append(_line("outbound send", "ok" if gate else "partial",
                      "the gate is open" if gate else "drafts only: the env gate is shut",
                      fix=None if gate else "HEYPHONY_SEND=allowed, then --send"))

    mail = views.voicemail()["count"] if voicemail_count is None else voicemail_count
    rows.append(_line("voicemail", "ok" if mail else "unknown",
                      "{} recording{}".format(mail, "" if mail == 1 else "s") if mail
                      else "none stored, which is not the same as none arriving"))

    return rows


def render(rows, on=True):
    """the block a person reads: the mark, a name, the reason, and the fix when there is one."""
    width = max(len(row["name"]) for row in rows) if rows else 8
    out = []
    for row in rows:
        head = "{} {}".format(paint(row["state"], row["state"], on), row["name"].ljust(width))
        out.append("{}  {}".format(head, row["why"]))
        if row.get("fix"):
            out.append("{}  {}".format(" " * 2, ("\x1b[2m" if on else "") + "\u2192 " + row["fix"]
                                       + ("\x1b[0m" if on else "")))
    return "\n".join(out)


def summary(rows):
    """one line at the end, because a person scrolling wants the verdict before the detail."""
    counts = {}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    worst = min((row["state"] for row in rows), key=lambda s: ORDER[s], default="ok")
    return {"counts": counts, "worst": worst,
            "verdict": {"ok": "everything here is proved",
                        "partial": "some of this is configured and none of it is proven yet",
                        "missing": "something is missing, and the fix is on its own line",
                        "unknown": "nothing has been tried, which is not the same as broken"}[worst]}


def payload(**kwargs):
    """the whole thing as one object, so `--status --json` is the same rows and not a second opinion."""
    rows = checks(**kwargs)
    return {"lines": rows, **summary(rows)}


def _line(name, state, why, fix=None, detail=None):
    row = {"name": name, "state": state, "why": why, "fix": fix}
    if detail:
        row["detail"] = detail
    return row


def _rc():
    """the written config, or an empty one: a host with no number is a normal host, not an error."""
    try:
        return sip.read_rc() or {}
    except Exception:
        return {}


def _did():
    """the did from the sip config, if one is written and has a number in it."""
    did = (_rc().get("telephony") or {}).get("did")
    return str(did) if did and str(did).startswith("+") else None


def _provider():
    return (_rc().get("telephony") or {}).get("provider")


def _ago(stamp):
    """epoch seconds into the shortest true phrase: '6 hours ago' beats a number nobody converts in their head."""
    try:
        seconds = int(float(stamp))
    except (TypeError, ValueError):
        return str(stamp)
    import time
    delta = max(0, int(time.time()) - seconds)
    for size, name in ((86400, "day"), (3600, "hour"), (60, "minute")):
        if delta >= size:
            count = delta // size
            return "{} {}{} ago".format(count, name, "" if count == 1 else "s")
    return "seconds ago"


def _last_message():
    try:
        rows = views.messages(limit=1)["rows"]
    except Exception:
        return None
    return str(rows[0].get("at")) if rows else None
