"""the state of this number as a person reads it: one line per rail, a mark, and why.

`heyphony status` answers a script. "is this number working" is a different question, and it has a
different shape: eight rails, a mark on each, and the shortest reason that is still true. so this is a
second rendering of the same evidence rather than a second set of facts.

the rails are the moments the package actually claims: a text in, a text out, a call answered by the
agent while it is happening, a call answered at all, a call the agent sits in on, a call placed, a
voicemail caught, a call forwarded. the "(live)" row is the one where the agent is a participant rather
than the number: that is a different capability from the carrier ringing, and it fails differently.

four marks, because three would lie. green is proof: a message stored, a call logged, a config written.
orange is shipped-but-unproven or half-wired, which is the honest state of most of this repo. red is
absent. dim is not-known-yet: nothing has been tried, so calling it broken would be as wrong as calling
it fine.
"""

import os
import sys

from src.linphone import sip
from src.manage import allow, inbox, views
from src.manage.outgoing import send
from src.setup import routes

MARKS = {
    "ok": ("\u2713", "32"),       # green
    "partial": ("\u26a0", "33"),  # orange
    "missing": ("\u2717", "31"),  # red
    "unknown": ("\u00b7", "2"),   # dim
}

ORDER = {"missing": 0, "partial": 1, "unknown": 2, "ok": 3}

# the eight rails, in the order a person debugs them: what comes in, then what goes out, then the two
# real-time rows, then the things that depend on somebody having called.
RAILS = [
    ("sms inbound", "texts reach this number and land somewhere a person can read"),
    ("sms outbound", "this number can send a text, through a provider path that is written"),
    ("call inbound (live)", "the agent answers a call while it is happening, not afterwards"),
    ("call inbound", "the number rings and the call is answered at all"),
    ("call outbound (live)", "the agent places a call and stays on it"),
    ("call outbound", "the number can place a call, with or without the agent on it"),
    ("voicemail catch", "somebody who was not answered becomes a recording"),
    ("call forwarding", "a call that nobody takes goes somewhere else on purpose"),
]


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


def paint(state, on=True):
    symbol, code = MARKS[state]
    return "\x1b[{}m{}\x1b[0m".format(code, symbol) if on else symbol


def marks(state, on=True):
    """the same mark twice: the four-state one, and the plain tick a copy-paste can read."""
    return paint(state, on), MARKS[state][0]


def context(inbox_rows=None, call_rows=None, rc=None, env=None, config=None, paths=None,
            voicemail_count=None, policy=None, home=None, trials=None):
    """everything the rails read, gathered once and overridable, so a test can describe a host."""
    env = os.environ if env is None else env
    config = _rc() if config is None else config
    rows = _rows(inbox_rows)
    did = (config.get("telephony") or {}).get("did") or None
    provider = (config.get("telephony") or {}).get("provider") or None
    return {
        "env": env,
        "config": config,
        "did": did,
        "provider": provider,
        "route": routes.ROUTES.get(provider or ""),
        "home": _home() if home is None else dict(home),
        "inbox": rows,
        "inbound_sms": [row for row in rows if row.get("channel") == "sms"
                        and row.get("direction") == "inbound"],
        "outbound_sms": [row for row in rows if row.get("channel") == "sms"
                         and row.get("direction") == "out"],
        "voicemail": [row for row in rows if row.get("channel") == "voicemail"],
        "voicemail_count": (len([row for row in rows if row.get("channel") == "voicemail"
                                 and row.get("direction") in ("inbound", "in")])
                            if voicemail_count is None else voicemail_count),
        "calls": _calls() if call_rows is None else call_rows,
        "paths": (send.PATHS.get(provider) if paths is None else paths) if provider else None,
        "policy": allow.load() if policy is None else policy,
        "trials": read_trials() if trials is None else list(trials),
    }


def checks(**overrides):
    """the eight rows, each from evidence this host can actually produce."""
    return rail_rows(context(**overrides))


def rail_rows(ctx):
    out = []
    for (name, means), rail in zip(RAILS, (_sms_in, _sms_out, _call_in_live, _call_in,
                                           _call_out_live, _call_out, _voicemail, _forwarding)):
        said = rail(ctx)
        state, why = said[0], said[1]
        fix = said[2] if len(said) > 2 else None
        row = {"name": name, "means": means, "state": state, "why": why}
        if fix:
            row["fix"] = fix
        out.append(row)
    return out


def _no_number(ctx):
    """the one refusal every rail shares: without a number nothing else can be true."""
    return ("missing", "no did is written on this host, so nothing can arrive or leave",
            "heyphony connect sip --voipms --did +1...")


def _sms_in(ctx):
    if not ctx["did"]:
        return _no_number(ctx)
    count = len(ctx["inbound_sms"])
    route = ctx["route"]
    if not route:
        return ("missing", "a did with no provider route, so there is nowhere for a text to land",
                "heyphony setup select sip")
    if count:
        newest = _newest(ctx["inbound_sms"])
        return ("ok", "{} text{} stored through the {} route{}".format(
            count, "" if count == 1 else "s", route["kind"], ", the newest " + newest if newest else ""))
    listed = len(ctx["policy"].get("allow_numbers") or [])
    if listed == 0 and ctx["policy"].get("mode") != "open":
        return ("missing", "the {} route is designed, and the allowlist is empty so nothing gets in".format(
            route["kind"]), "heyphony allow allow +1... for the people who should get through")
    return ("partial", "{} route designed, no text has ever arrived, which is not the same as working"
            .format(route["kind"]), "one real message from a phone settles it")


def _sms_out(ctx):
    if not ctx["did"]:
        return _no_number(ctx)
    path = ctx["paths"] or {}
    state = str(path.get("state") or "no path")
    sent = len(ctx["outbound_sms"])
    gate = ctx["env"].get("HEYPHONY_SEND") == "allowed"
    if state != "wired":
        return ("missing", "provider path for {}: {}".format(ctx["provider"], state),
                "heyphony send --paths names what is missing for this vendor")
    if sent and gate:
        return ("ok", "wired, the gate is open, and {} message{} have gone out".format(
            sent, "" if sent == 1 else "s"))
    if sent:
        return ("ok", "wired, and {} message{} have gone out; the gate is shut now, so a new send drafts"
                .format(sent, "" if sent == 1 else "s"), "HEYPHONY_SEND=allowed, then --send")
    return ("partial", "{} is wired and gated by HEYPHONY_SEND, nothing has been sent yet".format(
        ctx["provider"]), "heyphony send --to +1... --text 'one message' --send")


def _call_in(ctx):
    if not ctx["did"]:
        return _no_number(ctx)
    inbound = [call for call in ctx["calls"] if str(call.get("direction")) in ("in", "inbound")]
    if inbound:
        return ("ok", "{} call{} on record".format(len(inbound), "" if len(inbound) == 1 else "s"))
    if sip.rc_path().is_file():
        return ("partial", "a registration is written and no call has been logged: ringing is unproven",
                "ring the number from a phone and answer it once")
    return ("missing", "no registration written, so nothing can ring", "heyphony connect sip --voipms")


def _call_in_live(ctx):
    if not ctx["did"]:
        return _no_number(ctx)
    if not ctx["home"].get("live"):
        return ("missing", "this build has no live call lane: the src/live folder is absent",
                "the lane ships on the mcp branch: heyphony live --run")
    proved = _proved(ctx, "call inbound (live)")
    if proved:
        return ("ok", "a live-answered call on record, and the trial at {} settled it".format(
            _ago(proved.get("at"))))
    answered = [call for call in ctx["calls"]
                if str(call.get("direction")) in ("in", "inbound") and str(call.get("state") or "") in
                ("answered", "established")]
    if answered:
        return ("ok", "{} answered call{} on record, and the live lane is in this build".format(
            len(answered), "" if len(answered) == 1 else "s"))
    return ("partial", "the live lane ships here and no call has been answered through it yet",
            "heyphony live --run, then ring the number while it watches")


def _call_out(ctx):
    if not ctx["did"]:
        return _no_number(ctx)
    proved = _proved(ctx, "call outbound")
    if proved:
        return ("ok", "a call placed from this host at {}".format(_ago(proved.get("at"))))
    if not ctx["home"].get("callheavy"):
        return ("missing", "no dial lane on this host: the callheavy folder is absent",
                "the lane ships on the mcp branch: heyphony live --dial --to +1...")
    trunk = _trunk(ctx["env"])
    if trunk["complete"]:
        return ("partial", "the dial lane ships and the trunk env is complete; nothing has been dialled "
                "from this host yet", "heyphony voicemail --to +1... --message 'one line' --send")
    return ("partial", "the dial lane ships; the trunk env is missing {}, so a dial would refuse".format(
        ", ".join(trunk["missing"])), "set {} and try one call".format(", ".join(trunk["missing"])))


def _call_out_live(ctx):
    row = _call_out(ctx)
    if row[0] == "missing":
        return row
    trunk = _trunk(ctx["env"])
    if trunk["complete"]:
        return ("partial", "trunk env complete, no call placed and no room joined from this host yet",
                "heyphony live --dial --to +1... --run")
    return ("partial", "the lane ships; with the trunk env missing the agent cannot join the call",
            "set {} first".format(", ".join(trunk["missing"])))


def _voicemail(ctx):
    count = ctx["voicemail_count"]
    if count:
        return ("ok", "{} recording{} stored, readable with `heyphony open voicemail --play 1`".format(
            count, "" if count == 1 else "s"))
    return ("partial", "none stored, which is not the same as none arriving",
            "a missed call with the carrier's voicemail-to-email or folder pointed here")


def _forwarding(ctx):
    if not ctx["home"].get("forwarding"):
        return ("missing", "no forwarding rules in this build: src/forwarding.py is absent, the rules "
                "live on the new branch", "the forwarding module is not shipped on mcp")
    return ("partial", "a forwarding rule can be written here and no carrier has been made to follow one",
            "one no-answer rule to a second did is the first honest row")


# --- what `--test` may try ------------------------------------------------------------------------
# `--status` reads. `--test --run` provokes. the split is the whole point: a row is green because
# something happened, and the only way to make something happen is to do it. four of these eight rails
# cannot be provoked from the agent's own host at all, because the thing being tested is whether an
# outside phone can reach this number, so those name the human act instead of pretending to try.
TRIALS = {
    "sms inbound": {"can_try": False,
                    "needs": "a text from a phone that is not this number, sent while the catcher runs"},
    "sms outbound": {"can_try": True, "needs_target": True,
                     "how": "send one text to a number you can check",
                     "cmd": ["send", "--text", "heyphony trial: one text"]},
    "call inbound (live)": {"can_try": False,
                            "needs": "a call from outside while `heyphony live --run` watches"},
    "call inbound": {"can_try": False, "needs": "a call from a phone you hold"},
    "call outbound (live)": {"can_try": True, "needs_target": True, "needs_trunk": True,
                             "how": "dial with the agent in the room",
                             "cmd": ["live", "--dial"]},
    "call outbound": {"can_try": True, "needs_target": True, "needs_trunk": True,
                      "how": "place one call and speak one line",
                      "cmd": ["voicemail", "--message", "heyphony trial: one call"]},
    "voicemail catch": {"can_try": False, "needs": "a call from outside that nobody answers"},
    "call forwarding": {"can_try": True, "needs_module": "forwarding",
                        "how": "write one no-answer rule and see the carrier follow it"},
}


def plan(ctx, rail=None, target=None):
    """what `--test` would do, without doing it: the rails, and whether this host can provoke them."""
    out = []
    for row in rail_rows(ctx):
        name = row["name"]
        if rail and name != rail:
            continue
        spec = TRIALS[name]
        blocked = _blocked(name, spec, ctx, target)
        out.append({"rail": name, "state_now": row["state"], "why_now": row["why"],
                    "can_try": blocked is None, "how": spec.get("how"),
                    "blocked": blocked, "needs": spec.get("needs")})
    return out


def attempt(ctx, name, target=None, runner=None):
    """provoke one rail, and record whether it worked. nothing is recorded for a refusal."""
    spec = TRIALS.get(name)
    if spec is None:
        raise KeyError("no trail for rail: {}; known: {}".format(name, ", ".join(TRIALS)))
    blocked = _blocked(name, spec, ctx, target)
    if blocked:
        return {"rail": name, "tried": False, "why": blocked}
    command = list(spec["cmd"]) + (["--to", target] if spec.get("needs_target") else []) + ["--send"]
    if runner is None:
        runner = _run_cli
    ok, detail = runner(command)
    record_trial(name, ok, detail)
    return {"rail": name, "tried": True, "ok": bool(ok), "detail": detail, "cmd": " ".join(command)}


def _blocked(name, spec, ctx, target):
    """every reason a trial cannot run here, named the way the fix names it."""
    if not spec.get("can_try"):
        return spec.get("needs") or "not provocable from this host"
    if not ctx["did"]:
        return "no did is written on this host"
    if spec.get("needs_target") and not target:
        return "no target: pass --to +1... so somebody can confirm it arrived"
    if spec.get("needs_trunk"):
        trunk = _trunk(ctx["env"])
        if not trunk["complete"]:
            return "trunk env missing: " + ", ".join(trunk["missing"])
    if spec.get("needs_module") and not ctx["home"].get(spec["needs_module"]):
        return "the {} module is not in this build".format(spec["needs_module"])
    if name == "sms outbound":
        if not (ctx["paths"] or {}).get("state") == "wired":
            return "the provider path is not wired"
        if ctx["env"].get("HEYPHONY_SEND") != "allowed":
            return "the send gate is shut: HEYPHONY_SEND=allowed"
    return None


def _run_cli(command):
    """the one place an attempt becomes a real message or call: it shells the command that owns it."""
    import pathlib
    import subprocess
    here = pathlib.Path(__file__).resolve().parent.parent.parent
    binary = here / "bin" / "heyphony"
    try:
        run = subprocess.run([str(binary)] + command, capture_output=True, text=True, timeout=180)
    except Exception as error:
        return (False, str(error))
    detail = (run.stdout or run.stderr or "").strip().splitlines()
    return (run.returncode == 0, detail[-1] if detail else "no output")


def trials_path():
    """where an attempt is remembered: the same state directory the messages live in."""
    import os
    import pathlib
    override = os.environ.get("HEYPHONY_TRIALS")
    if override:
        return pathlib.Path(override)
    try:
        base = sip.data_dir()
    except Exception:
        base = pathlib.Path.home() / ".local" / "share" / "heyphony"
    return pathlib.Path(base) / "trials.jsonl"


def record_trial(rail, ok, detail, at=None):
    import json
    import time
    path = trials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"rail": rail, "ok": bool(ok), "detail": str(detail or "")[:400], "at": at or int(time.time())}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def read_trials():
    """every trial ever recorded, oldest first; unreadable lines are skipped rather than fatal."""
    import json
    path = trials_path()
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _proved(ctx, rail):
    """the newest trial for a rail, when it passed: that is evidence, and it is dated."""
    passed = [row for row in ctx.get("trials") or [] if row.get("rail") == rail and row.get("ok")]
    return passed[-1] if passed else None


def render(rows, on=True):
    """the block a person reads: the mark, the rail, the reason, and the fix when there is one."""
    width = max(len(row["name"]) for row in rows) if rows else 8
    out = []
    for row in rows:
        head = "{} {}".format(paint(row["state"], on), row["name"].ljust(width))
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
            "verdict": {"ok": "every rail here is proved",
                        "partial": "some rails are shipped and none of them is proved yet",
                        "missing": "something is absent, and the fix is on its own line",
                        "unknown": "nothing has been tried, which is not the same as broken"}[worst]}


def payload(**kwargs):
    """the whole thing as one object, so `--status --json` is the same rows and not a second opinion."""
    rows = checks(**kwargs)
    return {"lines": rows, **summary(rows)}


def _trunk(env):
    names = ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_SIP_TRUNK")
    missing = [name for name in names if not env.get(name)]
    return {"complete": not missing, "missing": missing}


def _home():
    """which lanes are in this build, read from the package rather than claimed here."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    return {"live": (root / "live" / "both.py").is_file(),
            "callheavy": (root / "callheavy").is_dir(),
            "voicemail": (root / "manage" / "outgoing" / "voicemail.py").is_file(),
            "forwarding": (root / "forwarding.py").is_file()}


def _rc():
    """the written config, or an empty one: a host with no number is a normal host, not an error."""
    try:
        return sip.read_rc() or {}
    except Exception:
        return {}


def _rows(inbox_rows):
    """the stored messages, which is the only place that knows direction: `views` is a person's inbox.

    nothing here is fetched or re-asked. this is the whole point of `--status`: it reads what is already
    on disk. anything that has to be provoked is `--test`.
    """
    if inbox_rows is not None:
        return list(inbox_rows)
    try:
        return list(inbox.read() or [])
    except Exception:
        return []


def _newest(rows):
    """the newest by `at`, because arrival order and storage order are not the same thing."""
    stamps = [row.get("at") for row in rows if row.get("at") is not None]
    return _ago(max(stamps, key=lambda value: _seconds(value))) if stamps else None


def _seconds(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _calls():
    try:
        return sip.calls(limit=200) or []
    except Exception:
        return []


def _ago(stamp):
    """epoch seconds into the shortest true phrase: '6 hours ago' beats a number nobody converts."""
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
