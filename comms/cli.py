"""comms: the umbrella command. it composes lanes and never reimplements one.

telephony registration lives in heyphony (/bin/heyphony). this command tells you
what the other folders need, catches their webhooks, and asks a lane for its plan.
"""
import argparse
import json
import sys

from comms import envelope, registry


def _out(obj):
    print(json.dumps(obj, indent=2, sort_keys=True))


def setup_payload(lane=None):
    lanes = registry.lanes()
    chosen = [lane] if lane else sorted(lanes)
    return {
        "what_this_is": "one envelope, many carriers. every folder is a lane with its own gate and its own honest state.",
        "lanes": {name: {"carrier": lanes[name]["carrier"], "intake": lanes[name]["intake"],
                         "relay": lanes[name]["relay"], "state": envelope.state_for(lanes[name])["state"],
                         "gate": list(envelope.gates(lanes[name]))}
                  for name in chosen},
        "telephony": "the voice and sms lanes are heyphony's: run `bin/heyphony --setup`",
        "refused": envelope.REFUSED,
        "rules": envelope.RULES,
    }


def cmd_setup(args):
    _out(setup_payload(args.lane))


def cmd_status(args):
    _out({"lanes": registry.states(), "reachable": registry.reachable()})


def cmd_inbox(args):
    from comms import number
    rows = number.inbox().read(since_days=args.since)
    if args.lane:
        rows = [r for r in rows if r.get("channel") == args.lane]
    _out({"messages": rows, "count": len(rows)})


def cmd_serve(args):
    from comms import catcher
    catcher.serve(port=args.port)


def cmd_join(args):
    from comms.registry import folders, _load
    mod = _load("meetings")
    _out(mod.join_plan(args.platform, args.meeting))


def cmd_watch(args):
    mod = registry._load("discord")
    _out(mod.watch_plan())


def cmd_go_live(args):
    mod = registry._load("streaming")
    _out(mod.go_live_plan(args.platform))


def cmd_signal(args):
    mod = registry._load("signal")
    _out(mod.registration_plan(args.path))


def cmd_audio(args):
    from comms import audio
    if args.audit:
        _out(audio.audit())
    else:
        _out({"meeting": audio.meeting_mic(args.meeting, client=args.client),
              "readiness": audio.readiness(), "stack": audio.STACK})


def cmd_signup(args):
    from comms import signup
    if args.devices:
        _out(signup.device_note())
    elif args.list or not args.service:
        _out({"services": signup.listing(), "legs": signup.LEGS, "refused": signup.REFUSED})
    else:
        _out(signup.plan(args.service))


def cmd_recognica(args):
    """the book itself: which shelf holds the owner, who is a person, who is another agent."""
    from comms.recognica import cards as cardbook, roles
    cards = cardbook.load()
    if args.owner:
        handles = []
        for item in args.owner:
            if ":" not in item:
                _out({"ok": False, "why": "say which handle: email:you@example.com or phone:+1555...",
                      "got": item})
                return 1
            channel, value = item.split(":", 1)
            handles.append((channel.strip(), value.strip()))
        cards, result = roles.make_owner(cards, handles=handles, name=args.name)
        if result.get("ok"):
            cardbook.save(cards)
        _out(result)
        return 0 if result.get("ok") else 1
    if args.agent:
        cards, result = roles.add_agent(cards, args.agent, {"email": args.email} if args.email else {})
        cardbook.save(cards)
        _out(result)
        return 0
    summary = roles.summary(cards)
    summary["cards"] = [{"id": c["id"], "name": c["name"], "shelf": cardbook.shelf(c),
                         "role": c.get("role"), "kind": c.get("kind"),
                         "channels": sorted(c.get("handles", {}))} for c in cards]
    summary["refused"] = cardbook.REFUSED
    _out(summary)
    return 0


def cmd_card(args):
    """the connecting card: one person, every lane, and the conversation they already had."""
    from comms.recognica import cards as cardbook
    cards = cardbook.load()
    if args.new:
        card = cardbook.new(args.new, note=args.note or "",
                            kind=cardbook.KIND_AGENT if args.agent else cardbook.KIND_HUMAN)
        cards.append(card)
        cardbook.save(cards)
        _out({"created": card["id"], "card": card})
        return
    if args.link:
        card_id, channel, handle = args.link
        cards, result = cardbook.link(cards, card_id, channel, handle)
        if result.get("linked"):
            cardbook.save(cards)
        _out(result)
        return
    if args.merge:
        keep_id, drop_id = args.merge
        cards, result = cardbook.merge(cards, keep_id, drop_id, args.confirm or "")
        if result.get("merged"):
            cardbook.save(cards)
        _out(result)
        return
    if args.digest:
        from comms import number
        _out(cardbook.digest(cards, args.digest, number.inbox().read()))
        return
    if args.show:
        card = next((c for c in cards if c["id"] == args.show), None)
        _out(card or {"card": None, "why": f"no card {args.show!r}"})
        return
    _out({"cards": [{"id": c["id"], "name": c["name"], "channels": sorted(c.get("handles", {}))} for c in cards],
          "refused": cardbook.REFUSED})


def cmd_doctor(args):
    _out({"lanes": registry.states(), "refused": envelope.REFUSED,
          "note": "a lane with credentials and no live message is designed, not verified"})


def build_parser():
    p = argparse.ArgumentParser(prog="comms", description="omnichannel, one envelope")
    p.add_argument("--setup", action="store_true")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("setup"); s.add_argument("--lane"); s.set_defaults(func=cmd_setup)
    st = sub.add_parser("status"); st.set_defaults(func=cmd_status)
    i = sub.add_parser("inbox"); i.add_argument("--lane"); i.add_argument("--since", type=float)
    i.set_defaults(func=cmd_inbox)
    w = sub.add_parser("serve"); w.add_argument("--port", type=int, default=8098)
    w.set_defaults(func=cmd_serve)
    j = sub.add_parser("join"); j.add_argument("--platform", default="zoom")
    j.add_argument("--meeting", required=True); j.set_defaults(func=cmd_join)
    wa = sub.add_parser("watch"); wa.set_defaults(func=cmd_watch)
    g = sub.add_parser("go-live"); g.add_argument("--platform", default="twitch")
    g.set_defaults(func=cmd_go_live)
    sg = sub.add_parser("signal"); sg.add_argument("--path", default="link-device")
    sg.set_defaults(func=cmd_signal)
    au = sub.add_parser("audio", help="the mic rail per room, and which parts are free software")
    au.add_argument("--meeting", default="zoom")
    au.add_argument("--client", default=None, help="a native client: zoom-client, linphone, baresip")
    au.add_argument("--audit", action="store_true")
    au.set_defaults(func=cmd_audio)
    su = sub.add_parser("signup", help="the four legs an account stands on, per service")
    su.add_argument("service", nargs="?")
    su.add_argument("--list", action="store_true")
    su.add_argument("--devices", action="store_true", help="what we concluded about driving a phone")
    su.set_defaults(func=cmd_signup)
    rg = sub.add_parser("recognica", help="the contact book: owner, people, agents")
    rg.add_argument("--owner", action="append", metavar="CHANNEL:HANDLE",
                    help="name the owner, repeatable, e.g. email:you@example.com")
    rg.add_argument("--name", help="the owner's name, when you are naming one")
    rg.add_argument("--agent", metavar="NAME", help="add another agent as an entry on the agents shelf")
    rg.add_argument("--email", help="that agent's email handle")
    rg.set_defaults(func=cmd_recognica)
    ca = sub.add_parser("card", help="one person, every lane: the connecting card")
    ca.add_argument("--new"); ca.add_argument("--note")
    ca.add_argument("--agent", action="store_true", help="this entry is software, so it goes on the agents shelf")
    ca.add_argument("--link", nargs=3, metavar=("ID", "CHANNEL", "HANDLE"))
    ca.add_argument("--merge", nargs=2, metavar=("KEEP", "DROP")); ca.add_argument("--confirm")
    ca.add_argument("--show"); ca.add_argument("--digest")
    ca.set_defaults(func=cmd_card)
    d = sub.add_parser("doctor"); d.set_defaults(func=cmd_doctor)
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--setup":
        argv = ["setup"] + argv[1:]
    args = build_parser().parse_args(argv)
    if not getattr(args, "func", None):
        build_parser().print_help()
        return 2
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
