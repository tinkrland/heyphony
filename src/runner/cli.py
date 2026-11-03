"""heyphony: telephony, made handleable by a process instead of a dashboard.

this command does one folder's job: a sip did, a provider, a registration, and the
messages and calls that came in. it imports nothing from the umbrella, so it stays
packageable on its own.
"""
import argparse
import json
import os
import pathlib
import pathlib
import sys

from src import __version__
from src.onramp import flow as getters
from src.manage import inbox
from src import providers
from src.linphone import sip
from src.manage import views

SETUP = {
    "what_this_is": "one number that rings a process: a sip did, a provider, a client on the host.",
    "steps": [
        {"do": "pick a provider and buy a did", "why": "flowroute and voip.ms both carry inbound sms cheaply",
         "cost": "about a dollar a month for the number"},
        {"do": "set HEYPHONY_SIP_DID and run `heyphony connect sip`", "why": "writes the client config, 0600, on the host",
         "note": "registration is one per number. a second machine registering it is a race, not a second line"},
        {"do": "start the client on the host", "why": "the number has to ring when no guest is running"},
        {"do": "point the provider's sms webhook at `heyphony serve`", "why": "texts never travel over sip"},
        {"do": "dial the echo test and text the number", "why": "a lane is proven by one real message, not a config file"},
    ],
    "lanes": {
        "voice": {"carrier": "sip over the internet", "gate": ["HEYPHONY_SIP_DID"], "state": "designed"},
        "sms": {"carrier": "provider webhook, never sip", "gate": ["HEYPHONY_SMS_TOKEN"], "state": "designed"},
    },
    "decided": sip.host_client(),
    "get": {"what": "rails the number itself unlocks, installed by the package that holds it",
            "commands": ["heyphony get signal"], "why": "signal wants a phone or an sms, and this is the package with both"},
    "rules": ["unset credentials close a lane", "the sip secret lives on the host, never in a burnable guest",
              "a did stays voip: refused for otp, refused for bulk outbound"],
}


def _out(obj):
    print(json.dumps(obj, indent=2, sort_keys=True))


def cmd_setup(args):
    if getattr(args, "what", None) == "areas":
        return cmd_setup_areas(args)
    if getattr(args, "what", None) == "select":
        return cmd_setup_select(args)
    _out(SETUP)


def cmd_setup_select(args):
    """`heyphony setup select sip`: a menu on a terminal, a json question for a process."""
    from src.setup import flow as flow
    interactive = (not getattr(args, "json", False)
                   and sys.stdin.isatty() and sys.stdout.isatty())
    rail = args.rail or "sip"
    if rail not in flow.RAILS:
        _out({"ok": False, "why": f"no such rail: {rail}", "rails": sorted(flow.RAILS)})
        return 1

    provider = getattr(args, "provider", None)
    if not provider and interactive:
        provider = flow.select("which provider (both about a dollar a month):", flow.PROVIDER_CHOICES)
    if not provider:
        _out(flow.needs("provider", flow.PROVIDER_CHOICES))
        return 0

    key = str(provider).lower().replace("voipms", "voip.ms").strip()
    if key not in providers.PROVIDERS:
        _out({"ok": False, "why": f"unknown provider: {provider}",
              "options": list(providers.PROVIDERS)})
        return 1

    did = getattr(args, "did", None)
    new = bool(getattr(args, "new", False) or getattr(args, "get_new", False))
    if not did and not new and interactive:
        source = flow.select("does this number already exist?", flow.DID_CHOICES)
        new = source == "new"
        if not new:
            did = flow.ask("the did, in e164 (+1...): ")
    if not did and not new:
        _out(flow.needs("did", flow.DID_CHOICES))
        return 0
    if did and not flow.valid_did(did):
        _out({"ok": False, "why": "that is not a number in e164 form",
              "got": did, "example": "+15551234567"})
        return 1
    try:
        plan = flow.plan_sip(key, did=did, new=new)
    except ValueError as exc:
        _out({"ok": False, "why": str(exc)})
        return 1
    if interactive:
        print(flow.render(plan))
    else:
        _out(plan)
    return 0


def cmd_app(args):
    """the launcher: tabs for caught texts, voicemail and calls, and one thread per person."""
    from src.runner import gui as launcher
    url = f"http://{args.host}:{args.port}/"
    if args.json:
        # a flag called json must not hold the terminal. it prints what the page would show and
        # exits without binding a port, so an agent can ask "what is in there" in one call.
        threads = launcher.threads(voicemail_dir=args.voicemail_dir)
        voice = launcher.voicemails(voicemail_dir=args.voicemail_dir)
        calls = launcher.calls()
        return _out({
            "launcher": url,
            "tabs": list(launcher.TABS),
            "reply": "drafts only",
            "serving": False,
            "voicemail_dir": args.voicemail_dir,
            "counts": {"threads": threads.get("count", 0),
                       "voicemail": voice.get("count", 0),
                       "calls": calls.get("count", 0),
                       "missed": calls.get("missed", 0)},
            "people": [t.get("peer") for t in threads.get("threads", [])][:10],
            "start_it": f"heyphony app --port {args.port}",
        })
    server = launcher.serve(port=args.port, host=args.host, voicemail_dir=args.voicemail_dir)
    print(f"heyphony app on {url}")
    print("tabs: caught messages, voicemail, calls. replies are drafted, never sent. ctrl-c to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("")
    finally:
        server.server_close()
    return 0


def cmd_import(args):
    """a forwarded carrier email becomes a caught message, audio and sidecar included."""
    from src.runner import gui as launcher
    from src.manage import views
    raw = pathlib.Path(args.file).read_text(errors="replace") if args.file else sys.stdin.read()
    answer = launcher.import_email(raw, save_dir=args.voicemail_dir or views.voicemail_dir())
    _out(answer)
    return 0 if answer.get("stored") else 1


def cmd_provision(args):
    """buy and arm a number from the cli, where a provider documents enough to script it."""
    from src.setup import numbering, provision
    if args.areas and args.provider != "anveo":
        _out({"ok": False, "why": "only anveo publishes a stock and price lookup we can call",
              "can_provision": ["anveo"]})
        return 1
    if args.numbering:
        country = args.numbering
        _out({"numbering": numbering.advice(country),
              "ranges": [r for r in numbering.UK_RANGES if r["kind"] in ("mobile", "business")]
              if country.upper() == "GB" else None})
        return 0
    if args.areas:
        from src.setup import provision
        answer = provision.areas(did_type=args.did_type, country_id=args.country_id,
                                 state_id=args.state_id, area_code=args.area_code,
                                 area_name=args.area_name)
        _out(answer)
        return 0 if answer.get("ok") else 1
    if args.provider not in ("anveo",):
        _out({"ok": False, "provider": args.provider,
              "why": "only anveo documents a whole chain we can call: areas, order, and arming sms by e164",
              "elsewhere": "the others order in a browser, then their hook is `heyphony hooks <provider>`",
              "can_provision": ["anveo"]})
        return 1
    from src.setup import routes
    sms_url = args.sms_url
    if sms_url in (None, "auto"):
        sms_url = routes.paste_url("anveo", args.base)
    answer = provision.plan(args.area_code, did_type=args.did_type, rate_plan=args.rate_plan,
                            sms_url=sms_url, title=args.title, apply=args.apply,
                            test=args.test, country_id=args.country_id, state_id=args.state_id,
                            area_name=args.area_name, purchase=args.purchase)
    _out(answer)
    if not (args.apply or args.purchase):
        return 0
    return 0 if answer.get("ok") else 1


def cmd_hooks(args):
    """the url to paste, and for providers with an api, the call that sets it."""
    from src.setup import routes
    if not getattr(args, "provider", None):
        _out({"providers": [{"provider": name, "kind": v["kind"],
                             "paste_url": routes.hook(name, args.base)["paste_url"] or "email"}
                            for name, v in routes.ROUTES.items()],
              "base": args.base,
              "how": "heyphony hooks <provider> --base https://your-host:8099"})
        return 0
    try:
        if getattr(args, "apply", False):
            answer = routes.apply_hook(args.provider, args.base, getattr(args, "did", None))
            _out(answer)
            return 0 if answer.get("applied") else 1
        _out(routes.hook(args.provider, args.base, getattr(args, "did", None)))
        return 0
    except KeyError as exc:
        _out({"ok": False, "why": str(exc).strip("'\"")})
        return 1


def cmd_setup_areas(args):
    """which area codes have stock, and what a month of each costs: the choice before the order."""
    from src.setup import provision
    answer = provision.areas_menu(area_code=args.area_code, area_name=args.area_name,
                                  country_id=args.country_id, state_id=args.state_id,
                                  did_type=args.did_type)
    _out(answer)
    return 0 if answer.get("ok") else 1


def cmd_status(args):
    _out({"rc": str(sip.rc_path()), "rc_present": sip.rc_path().is_file(),
          "provider": providers.profile("voip.ms")["provider"],
          "sms_inbox": inbox.count(), "host_client": sip.host_client()["client"],
          "unread": sum(1 for r in views.messages(limit=500)["rows"] if r["unread"]),
          "voicemail": views.voicemail()["count"]})


def cmd_connect(args):
    provider = args.provider or ("voip.ms" if args.voipms else "flowroute" if args.flowroute else None)
    if not provider:
        raise SystemExit("connect sip needs --provider, or --voipms / --flowroute")
    providers.profile(provider)
    path = sip.write_rc(provider, args.did, args.username, args.password, args.server)
    from src.setup import numbering
    answer = {"rc": str(path), "provider": provider, "did": args.did, "endpoint": args.on,
              "plan": sip.connection_plan(args.did, args.on),
              "next": "start the client on the host, then heyphony status",
              "numbering": numbering.look(args.did)}
    warning = numbering.warn(args.did)
    if warning:
        answer["warning"] = warning
    _out(answer)


def cmd_calls(args):
    rows = sip.calls(missed_only=args.missed, limit=args.limit)
    _out({"calls": rows, "count": len(rows)})


def cmd_inbox(args):
    rows = inbox.read(since_days=args.since)
    _out({"messages": [r for r in rows if r.get("channel") == "sms"], "count": len(rows)})


def cmd_serve(args):
    from src.manage import catcher
    catcher.serve(port=args.port, token=args.token)


def cmd_open(args):
    """the inbox, the call log, the voicemail: json the agent can walk one item at a time."""
    if args.what == "messages":
        _out(views.messages(unread=args.unread, since_days=args.since, thread=args.thread,
                            limit=args.limit, show=args.show, do_mark=args.mark_read))
    elif args.what == "calls":
        _out(views.calls(missed=args.missed, limit=args.limit, show=args.show))
    elif args.what == "voicemail":
        _out(views.voicemail(limit=args.limit, show=args.show, play=args.play))
    else:
        _out({"messages": views.messages(limit=args.limit, unread=args.unread, since_days=args.since),
              "calls": views.calls(missed=args.missed, limit=args.limit),
              "voicemail": views.voicemail(limit=args.limit)})


def cmd_get(args):
    """the one command an agent runs once it has a number: heyphony get signal."""
    if args.list or not args.name:
        recipes = getters.available()
        _out({"getters": {n: {"state": r["state"],
                              "paths": {p: {"needs_number": bool(v.get("needs_number")),
                                            "gate_env": v.get("gate_env")}
                                        for p, v in r["paths"].items()}}
                          for n, r in recipes.items()},
              "usage": "heyphony get <name> [--path <one of that getter's paths>] [--run]"})
        return
    _out(getters.run(args.name, path=args.path, dry=not args.run))


LOOKUP_MODES = ("line", "support", "probes", "fallback")

# a number is read as a line, an address as an address, a username as a handle. the key says which,
# because printing an email under a key called "line" is the kind of small wrongness that teaches
# people to stop reading the output
SUBJECT_KEYS = {"number": "line", "email": "address", "username": "handle"}


def _lookup_args(rest):
    """`--lookup <number> [mode]`, with the mode optional because the number is the point."""
    parsed = {"number": None, "mode": "all", "platform": None}
    if rest and rest[0] == "eval":
        return {"number": None, "mode": "eval", "platform": None}
    words = list(rest)
    if "--platform" in words:
        at = words.index("--platform")
        if at + 1 < len(words):
            parsed["platform"] = words[at + 1]
            del words[at:at + 2]
    for word in words:
        if word.startswith("-"):
            continue
        if parsed["number"] is None:
            parsed["number"] = word
        elif word in LOOKUP_MODES:
            parsed["mode"] = word
        else:
            parsed["mode"] = word
    return parsed


def cmd_lookup(args):
    """what a number is, from the plan that issues it, and the probe that would go further."""
    from src.lookup import classify, evalrun, support
    number = args.get("number") if isinstance(args, dict) else getattr(args, "number", None)
    mode = (args.get("mode") if isinstance(args, dict) else getattr(args, "mode", None)) or "all"
    platform = args.get("platform") if isinstance(args, dict) else getattr(args, "platform", None)
    if number == "eval":
        number, mode = None, "eval"
    if mode == "eval":
        report = evalrun.run()
        _out({k: report[k] for k in ("cases", "pass", "fail", "unknown_rate", "note", "how_to_read")}
             | {"overreach": len(report["overreach"]),
                "failures": [{k: row[k] for k in ("id", "wrong", "got", "expected")}
                             for row in report["failures"]]})
        return 0 if report["fail"] == 0 and not report["overreach"] else 1
    if not number:
        _out({"ok": False, "why": "lookup needs a number",
              "usage": "heyphony --lookup +447700900123 [line|support|probes]",
              "modes": list(LOOKUP_MODES)})
        return 1
    if mode in ("support", "services", "all"):
        answer = support.support(number, platform)
        if mode == "support":
            _out(answer)
            key = SUBJECT_KEYS.get(answer.get("kind") or "number", "line")
            return 0 if answer[key]["valid"] else 1
        single = classify.classify(number, platform)
        answer = {"ok": True, "all": answer,
                  SUBJECT_KEYS.get(single.get("kind") or "number", "line"): single}
    elif mode == "fallback":
        single = support.support(number, platform)["fallback"]
        single["subject"] = number
        _out({"ok": True, "fallback": single})
        return 0
    elif mode == "probes":
        answer = support.probe_plan(number)
        _out(answer)
        return 0 if answer.get("ok") else 1
    else:
        single = classify.classify(number, platform)
        answer = {"ok": True, SUBJECT_KEYS.get(single.get("kind") or "number", "line"): single}
    _out(answer)
    return 0 if answer.get("ok", True) else 1


def cmd_voicemail(args):
    """one call, one person, a message spoken after whatever answers picks up."""
    from src.manage.outgoing import voicemail
    if not args.to or not args.message:
        _out({"placed": False, "why": "voicemail needs --to and --message",
              "usage": 'heyphony voicemail --to +15551234567 --message "sorry we missed you" --send',
              "refuses": voicemail.REFUSES})
        return 1
    answer = voicemail.leave(args.to, args.message, wait=args.wait, allow=bool(args.send))
    if args.curl:
        answer["curl"] = voicemail.as_curl(voicemail.dial_request(dict(os.environ), args.to,
                                                                  answer["room"]))
    if args.agent:
        state = pathlib.Path(os.environ.get("HEYPHONY_STATE")
                             or pathlib.Path.home() / ".local/share/telephony")
        state.mkdir(parents=True, exist_ok=True)
        script = state / "voicemail_agent.py"
        script.write_text(voicemail.agent_script(args.message, wait=args.wait))
        os.chmod(script, 0o600)
        answer["agent_script"] = str(script)
        answer["agent_command"] = f"python {script} dev"
    _out(answer)
    return 0 if answer.get("sent") else 1


def cmd_group(args):
    """a conversation with two to four named people, one message at a time."""
    from src.manage import groups
    args.group = args.group or getattr(args, "target", None)
    if args.action == "new":
        members = []
        for chunk in args.with_ or []:
            name, _, number = chunk.partition("=")
            members.append({"name": name.strip(), "number": number.strip() or name.strip()})
        answer = groups.create(args.name, members, number=getattr(args, "number", None))
    elif args.action == "list":
        answer = groups.listing()
    elif args.action in ("show", "messages"):
        answer = groups.show(args.group)
        if answer.get("ok"):
            answer["thread"] = groups.thread(args.group, messages=None)["rows"]
    elif args.action in ("say", "reply"):
        if not args.text:
            _out({"sent": 0, "why": "say needs --text"})
            return 1
        provider = args.provider or os.environ.get("HEYPHONY_SIP_PROVIDER") or "voip.ms"
        from_number = os.environ.get("HEYPHONY_SIP_DID")
        if not from_number:
            _out({"sent": 0, "why": "no sender number",
                  "how": "set HEYPHONY_SIP_DID to the did this provider holds"})
            return 1
        verb = groups.reply if args.action == "reply" else groups.say
        extra = {"replying": args.replying} if args.action == "reply" else {}
        answer = verb(args.group, args.text, provider=provider, from_number=from_number,
                      allow=bool(args.send), tag=not bool(getattr(args, "no_tag", False)), **extra)
    else:
        answer = {"ok": False, "why": "group takes new, list, show, say or reply"}
    _out(answer)
    return 0 if answer.get("ok") or answer.get("count") is not None else 1


def cmd_send(args):
    """one outbound text, drafted by default and sent only when the gate and the flag both agree."""
    if args.paths:
        from src.manage.outgoing import send as outbox
        _out(outbox.path_index())
        return 0
    if not args.to or not args.text:
        _out({"sent": False, "why": "send needs --to and --text, or --paths to list the providers",
              "usage": 'heyphony send --to +15551234567 --text "on my way" --send'})
        return 1
    from src.manage.outgoing import send as outbox
    provider = args.provider or os.environ.get("HEYPHONY_SIP_PROVIDER") or "voip.ms"
    from_number = args.sender or os.environ.get("HEYPHONY_SIP_DID")
    if not from_number:
        _out({"sent": False, "why": "no sender number",
              "how": "pass --from +1... or set HEYPHONY_SIP_DID to the did this provider holds"})
        return 1
    answer = outbox.send(provider=provider, from_number=from_number, to=args.to, text=args.text,
                         allow=bool(args.send), store=not args.no_store)
    _out(answer)
    return 0 if answer.get("sent") else 1


def cmd_doctor(args):
    _out({"host_client": sip.host_client(), "rc_present": sip.rc_path().is_file(),
          "inbox": inbox.count(),
          "note": "nothing here has placed a call yet. a lane with credentials and no live call is designed, not verified"})


def routes_base():
    from src.setup import routes
    return routes.BASE


def build_parser():
    p = argparse.ArgumentParser(prog="heyphony", description="telephony an agent can hold")
    # --version is answered here rather than by a caller reading __init__.py, so an install can be
    # checked with the command the install put on the path: `heyphony --version`.
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--setup", action="store_true", help="print the telephony setup plan as json and stop")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("setup", help="the plan, `setup select sip` to walk it, or `setup areas` to choose one")
    s.add_argument("what", nargs="?", choices=["select", "plan", "areas"])
    s.add_argument("rail", nargs="?")
    s.add_argument("--provider")
    s.add_argument("--did", help="a did you already hold, in e164")
    s.add_argument("--new", "--get-new", dest="new", action="store_true",
                   help="order one in the browser instead")
    s.add_argument("--json", action="store_true", help="json even on a terminal")
    s.add_argument("--area-code", help="with `setup areas`: the area code an agent wants to see")
    s.add_argument("--area-name", help="with `setup areas`: a city or region fragment")
    s.add_argument("--country-id", help="with `setup areas`: anveo's country id")
    s.add_argument("--state-id", help="with `setup areas`: anveo's state id")
    s.add_argument("--did-type", default="GEOGRAPHIC",
                   choices=["GEOGRAPHIC", "NATIONAL", "TOLLFREE", "MOBILE"])
    s.set_defaults(func=cmd_setup)
    st = sub.add_parser("status"); st.set_defaults(func=cmd_status)
    c = sub.add_parser("connect")
    c.add_argument("target", choices=["sip"])
    c.add_argument("--provider"); c.add_argument("--voipms", action="store_true")
    c.add_argument("--flowroute", action="store_true"); c.add_argument("--did", required=True)
    c.add_argument("--username", required=True); c.add_argument("--password", required=True)
    c.add_argument("--server"); c.add_argument("--on", choices=["host", "guest"], default="host")
    c.set_defaults(func=cmd_connect)
    k = sub.add_parser("calls"); k.add_argument("--missed", action="store_true")
    k.add_argument("--limit", type=int, default=50); k.set_defaults(func=cmd_calls)
    i = sub.add_parser("inbox"); i.add_argument("--since", type=float, default=None)
    i.set_defaults(func=cmd_inbox)
    w = sub.add_parser("serve"); w.add_argument("--port", type=int, default=8099)
    w.add_argument("--token"); w.set_defaults(func=cmd_serve)
    o = sub.add_parser("open", help="read the inbox, the call log or the voicemail")
    o.add_argument("what", nargs="?", default="all", choices=["messages", "calls", "voicemail", "all"])
    o.add_argument("--unread", action="store_true")
    o.add_argument("--since", type=float, default=None, help="days back")
    o.add_argument("--thread", default=None)
    o.add_argument("--limit", type=int, default=20)
    o.add_argument("--show", type=int, default=None, help="expand row N")
    o.add_argument("--mark-read", type=int, nargs="*", default=None, dest="mark_read")
    o.add_argument("--missed", action="store_true")
    o.add_argument("--play", type=int, default=None, help="play voicemail row N")
    o.set_defaults(func=cmd_open)

    g = sub.add_parser("get", help="open a rail that needs the number this host already holds")
    g.add_argument("name", nargs="?")
    g.add_argument("--path", default=None, help="phone-signup (default) | link-desktop | register-number")
    g.add_argument("--run", action="store_true", help="actually execute the install steps")
    g.add_argument("--list", action="store_true")
    g.set_defaults(func=cmd_get)
    ap = sub.add_parser("app", help="the launcher: caught messages, voicemail and calls as tabs")
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--voicemail-dir")
    ap.add_argument("--json", action="store_true",
                    help="print what the page would show and exit, instead of serving")
    ap.set_defaults(func=cmd_app)
    im = sub.add_parser("import", help="turn a forwarded carrier email into a caught message")
    im.add_argument("--file", help="an .eml or raw message; stdin when omitted")
    im.add_argument("--voicemail-dir")
    im.set_defaults(func=cmd_import)
    pv = sub.add_parser("provision", help="order a number and arm its texts, where the provider is scriptable")
    pv.add_argument("--provider", default="anveo", choices=["anveo"])
    pv.add_argument("--area-code")
    pv.add_argument("--area-name")
    pv.add_argument("--areas", action="store_true", help="list areas with stock and prices, then stop")
    pv.add_argument("--purchase", action="store_true",
                    help="parked: the order is the payment step, and no payment rail is wired")
    pv.add_argument("--did-type", default="GEOGRAPHIC")
    pv.add_argument("--rate-plan", default="SU")
    pv.add_argument("--numbering", metavar="ISO",
                    help="say what to order in a country before ordering anything (GB, SE, LT, PL, AU, NL)")
    pv.add_argument("--country-id")
    pv.add_argument("--state-id")
    pv.add_argument("--title", default="heyphony")
    pv.add_argument("--sms-url", help="defaults to the anveo paste url for this host")
    pv.add_argument("--base", default=routes_base(), help="the host a provider will post texts to")
    pv.add_argument("--test", action="store_true", help="anveo's TEST flag: sandbox the request")
    pv.add_argument("--apply", action="store_true",
                    help="run the free steps: area stock and prices, and the prepared order")
    pv.set_defaults(func=cmd_provision)
    hk = sub.add_parser("hooks", help="the url and the setting that makes one provider's texts arrive")
    hk.add_argument("provider", nargs="?")
    hk.add_argument("--base", default=routes_base())
    hk.add_argument("--did")
    hk.add_argument("--apply", action="store_true", help="set it over the provider's api, when that exists")
    hk.set_defaults(func=cmd_hooks)
    lk = sub.add_parser("lookup", help="what a number is: line class, text, service support")
    lk.add_argument("number")
    lk.add_argument("--platform", choices=["signal", "whatsapp"], default=None,
                    help="which platform's username rules to apply, when the string is a username")
    lk.add_argument("mode", nargs="?", default="all",
                    choices=list(LOOKUP_MODES) + ["all", "eval"],
                    help="`eval` runs the labelled fixtures instead of a number")
    lk.set_defaults(func=cmd_lookup)

    vm = sub.add_parser("voicemail", help="place one call and leave a spoken message")
    vm.add_argument("--to")
    vm.add_argument("--message")
    vm.add_argument("--wait", type=int, default=18,
                    help="seconds after the call is answered before speaking (no amd on this rail)")
    vm.add_argument("--send", action="store_true", help="actually dial, with HEYPHONY_CALL=allowed")
    vm.add_argument("--curl", action="store_true", help="print the livekit dial as a curl line")
    vm.add_argument("--agent", action="store_true", help="write the tts worker that speaks the message")
    vm.set_defaults(func=cmd_voicemail)

    gr = sub.add_parser("group", help="a small named conversation, one message per member")
    gr.add_argument("action", choices=["new", "list", "show", "say", "reply"])
    gr.add_argument("--name")
    gr.add_argument("--with", dest="with_", action="append", metavar="NAME=+1555...",
                    help="a member, repeated (max four)")
    gr.add_argument("target", nargs="?", help="group id or name, the same thing --group takes")
    gr.add_argument("--group", help="group id or name")
    gr.add_argument("--text")
    gr.add_argument("--number", metavar="+1555...",
                    help="a did of the group's own, so replies arrive addressed instead of inferred")
    gr.add_argument("--provider")
    gr.add_argument("--send", action="store_true", help="actually send, with HEYPHONY_SEND=allowed")
    gr.add_argument("--no-tag", action="store_true",
                    help="send the body without the group's code on the end")
    gr.add_argument("--replying", metavar="+1555...",
                    help="the member whose text you are answering, recorded rather than messaged singly")
    gr.set_defaults(func=cmd_group)

    s = sub.add_parser("send", help="one outbound text: drafted unless --send, gated by HEYPHONY_SEND")
    s.add_argument("--to", help="one recipient in e164. a list is refused, on purpose")
    s.add_argument("--text", help="the body. 1600 characters is the ceiling")
    s.add_argument("--from", dest="sender", help="the did this provider holds (or HEYPHONY_SIP_DID)")
    s.add_argument("--provider", help="defaults to HEYPHONY_SIP_PROVIDER, then voip.ms")
    s.add_argument("--paths", action="store_true",
                   help="list every provider and what its outbound story is, then stop")
    s.add_argument("--send", action="store_true",
                   help="actually send, which also needs HEYPHONY_SEND=allowed in the environment")
    s.add_argument("--no-store", action="store_true", help="do not record a sent message in the inbox")
    s.set_defaults(func=cmd_send)
    d = sub.add_parser("doctor"); d.set_defaults(func=cmd_doctor)
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--setup":
        argv = ["setup"] + argv[1:]
    if argv and argv[0] == "--lookup":
        return cmd_lookup(_lookup_args(argv[1:]))
    if argv and argv[0] == "lookup":
        return cmd_lookup(_lookup_args(argv[1:]))
    if argv[:2] == ["setup", "provision"]:
        argv = ["provision"] + argv[2:]
    if argv[:2] == ["setup", "--select"]:
        argv = ["setup", "select"] + argv[2:]
    args = build_parser().parse_args(argv)
    if not getattr(args, "func", None):
        build_parser().print_help()
        return 2
    return args.func(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
