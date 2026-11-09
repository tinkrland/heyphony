"""callheavy: our own calls, arranged around a task instead of a script.

every subcommand prints one json object and exits. nothing prompts, because the caller may be a program
and a prompt is a hang. the two verbs that matter are `plan`, which dials nothing, and `dial`, which
needs `--run` and a named authoriser before it will ring anybody.
"""
import argparse
import json
import os
import pathlib
import sys
import time

from callheavy.src import audio, calle, dial, host, pump, task as tasks

STATE = pathlib.Path(os.environ.get("HEYPHONY_CALLHEAVY_DIR")
                     or "~/.local/share/telephony/callheavy").expanduser()


def _read_json(path):
    return json.loads(pathlib.Path(path).read_text()) if path else None


VIA = ("callheavy", "calle")

# what each rail is and what it costs, printed with every plan so the choice is never invisible
RAILS = {
    "callheavy": {"rings_from": "this machine, over our own baresip and the did it holds",
                  "spends": "the did's per minute rate, to the carrier the owner already pays",
                  "returns": "the call's own facts (ringing, established, closed) and the audio path, but no "
                             "transcript and no extracted result: those need a speech model this repo does not ship",
                  "needs": ["a running baresip with ctrl_tcp (callheavy host)", "HEYPHONY_CALL is not read here; "
                            "--authorized and --run are the consent"]},
    "calle": {"rings_from": "a hosted service (api.heycall-e.com), with their voice agent doing the talking",
              "spends": "the owner's call-e credits, on the owner's own key",
              "returns": "the call, a transcript and a result extracted into the schema, in one round trip",
              "needs": ["CALLE_API_KEY in the environment", "HEYPHONY_CALL=allowed",
                        "a closed flat result schema (at most 32 string, boolean, integer or number fields)",
                        "--authorized and --run"]},
}


def _via_note(via):
    return {"via": via, **RAILS[via]}


def _task(args):
    return tasks.task(args.goal, _read_json(args.schema), args.success, args.notes, args.language)


def _record_path(name):
    STATE.mkdir(parents=True, exist_ok=True)
    return STATE / f"{name}.json"


def _store(item, name):
    path = _record_path(name)
    path.write_text(json.dumps(item, indent=2, sort_keys=True))
    os.chmod(path, 0o600)
    return str(path)


def cmd_host(args):
    answer = host.write(args.did, args.user, args.password, args.sip_host, home=args.home,
                        platform=getattr(args, "platform", None), port=args.port, dry=args.dry)
    return answer, 0


def cmd_plan(args):
    item = _task(args)
    if args.via == "calle":
        return _calle_plan(args, item)
    missing = tasks.clarifications(item, args.to)
    if missing:
        return {"ok": False, "problems": missing}, 1
    return {"ok": True, "task": item, "dial": f"sip:{args.to}", **_via_note("callheavy"),
            "socket": f"{args.socket}", "record": str(STATE),
            "note": "nothing was dialled. `dial --via callheavy --run` places it, and only then does a phone ring"}, 0


def _calle_inputs(args):
    schema = _read_json(args.schema)
    goal = args.goal
    return goal, schema


def _calle_plan(args, item, idem=None):
    goal, schema = _calle_inputs(args)
    found = calle.problems(goal, args.to, schema, getattr(args, "region", None))
    if found:
        return {"ok": False, "via": "calle", "problems": found}, 1
    key_ = idem or calle.idempotency_key(goal, args.to, schema)
    return {"ok": True, "sending": False, **_via_note("calle"),
            "request": calle.request_body(goal, args.to, schema, getattr(args, "region", None),
                                          args.language, None, None, args.notes),
            "idempotency_key": key_, "endpoint": calle.base() + "/v2/calls", "gate": calle.gate(),
            "note": "nothing was sent. `dial --via calle --run` creates the call, and only then is anyone rung"}, 0


def _calle_dial(args, item):
    plan, code = _calle_plan(args, item)
    if code:
        return plan, code
    if not args.authorized:
        return {"ok": False, "via": "calle", "problems": [{"needs": "authorized", "flag": "--authorized",
                "why": "a call is somebody's phone ringing; the record says who asked for it"}]}, 1
    plan["authorized_by"] = args.authorized
    if not args.run:
        plan["note"] = "plan only. --run creates the call"
        return plan, 0
    shut = calle.gate()
    if shut["closed"]:
        plan.update({"ok": False, "drafted": True, "gate": shut,
                     "note": "the gate is shut, so nothing was sent and nobody was rung"})
        return plan, 1
    goal, schema = _calle_inputs(args)
    try:
        created = calle.create(goal, args.to, schema, plan["idempotency_key"], region=getattr(args, "region", None),
                               locale=args.language, notes=args.notes)
        call_id = created.get("id")
        snapshot, timed_out = (created, False)
        if call_id and not args.no_wait:
            snapshot, timed_out = calle.wait(call_id, timeout=args.wait)
    except calle.ApiError as error:
        return {"ok": False, "via": "calle", "error": {"status": error.status, "code": error.code,
                "message": error.message, "details": error.details}, "authorized_by": args.authorized,
                "idempotency_key": plan["idempotency_key"]}, 1
    record = {**calle.shape(snapshot), "authorized_by": args.authorized,
              "idempotency_key": plan["idempotency_key"], "waited": not args.no_wait,
              "timed_out": timed_out,
              "resume": f"callheavy status --via calle --id {call_id}" if call_id else None}
    record["record"] = _store(record, f"calle-{int(time.time())}")
    return {"ok": snapshot.get("status") not in ("failed", "canceled"), **record}, 0


def cmd_dial(args):
    item = _task(args)
    if args.via == "calle":
        return _calle_dial(args, item)
    missing = tasks.clarifications(item, args.to)
    if missing:
        return {"ok": False, "problems": missing}, 1
    if not args.authorized:
        return {"ok": False, "problems": [{"needs": "authorized", "flag": "--authorized",
                                          "why": "a call is somebody's phone ringing; the record says "
                                                 "who asked for it"}]}, 1
    target = f"sip:{args.to}"
    if not args.run:
        return {"ok": True, "sending": False, "dial": target, "socket": args.socket, **_via_note("callheavy"),
                "task": item, "authorized_by": args.authorized,
                "note": "plan only. --run sends the dial to baresip"}, 0

    host_name, _, port = args.socket.partition(":")
    result = dial.dial(target, host=host_name or "127.0.0.1", port=int(port or 4444),
                       settle=args.settle)
    record = {"via": "callheavy", "task": item, "authorized_by": args.authorized, **result,
              "result_status": "not_applicable", "result": None, "transcript": [],
              "result_status_why": "this rail places the call and carries its audio, but turning audio into "
                                   "a transcript needs a speech model this repo does not ship. use `prompt` on "
                                   "a transcript you made, or --via calle for one in a single round trip"}
    record["record"] = _store(record, f"{args.to.lstrip('+')}-{int(time.time())}")
    return record, 0 if result.get("accepted") else 1


def cmd_status(args):
    """read one hosted call by id. a long call returns an id, and this is how it is picked up again."""
    if args.via != "calle":
        return {"ok": False, "problems": [{"needs": "via", "why": "only the hosted rail has a call id to ask about; "
                "a call on our own rail is a record file under " + str(STATE)}]}, 1
    if not calle.key():
        return {"ok": False, "problems": [{"needs": calle.KEY_ENV, "why": "reading a call needs the owner's key"}]}, 1
    try:
        snapshot = calle.get(args.id)
    except calle.ApiError as error:
        return {"ok": False, "via": "calle", "error": {"status": error.status, "code": error.code,
                "message": error.message}}, 1
    return {"ok": True, **calle.shape(snapshot)}, 0


def cmd_cancel(args):
    if args.via != "calle":
        return {"ok": False, "problems": [{"needs": "via", "why": "own-rail calls end with `hangup`"}]}, 1
    shut = calle.gate()
    if shut["closed"]:
        return {"ok": False, "drafted": True, "gate": shut, "note": "the gate is shut, so nothing was sent"}, 1
    try:
        return {"ok": True, **calle.shape(calle.cancel(args.id))}, 0
    except calle.ApiError as error:
        return {"ok": False, "via": "calle", "error": {"status": error.status, "code": error.code,
                "message": error.message}}, 1


def cmd_mic(args):
    if args.wav:
        return {"ok": True, **audio.browser_mic(args.wav, args.platform)}, 0
    return {"ok": True, **audio.readiness(args.platform)}, 0


def cmd_room(args):
    return {"ok": True, **audio.publish(), "bridge": audio.bridge_plan()}, 0


def cmd_result(args):
    schema = _read_json(args.schema)
    source = _read_json(args.transcript) or {}
    extracted = _read_json(args.result) if args.result else None
    envelope = tasks.envelope(extracted, schema, transcript=source.get("transcript"),
                              outcome=source.get("call_outcome"))
    return {"ok": envelope["result_status"] == "available", **envelope}, 0


def cmd_prompt(args):
    item = _task(args)
    transcript = (_read_json(args.transcript) or {}).get("transcript") or []
    return {"ok": True, "prompt": tasks.extract_prompt(item, transcript)}, 0


def build(argv=None):
    parser = argparse.ArgumentParser(prog="callheavy",
                                     description="our own calls, arranged around a task")
    sub = parser.add_subparsers(dest="cmd")

    host_p = sub.add_parser("host", help="write the baresip config and accounts this lane drives")
    host_p.add_argument("--did", required=True)
    host_p.add_argument("--user", required=True)
    host_p.add_argument("--password", required=True)
    host_p.add_argument("--sip-host", required=True, help="the provider's sip hostname, not a sentence")
    host_p.add_argument("--home", help="where the baresip directory is")
    host_p.add_argument("--platform", choices=sorted(host.HOSTS))
    host_p.add_argument("--port", type=int, default=host.CTRL_PORT)
    host_p.add_argument("--dry", action="store_true", help="print the files instead of writing them")
    host_p.set_defaults(handler=cmd_host)

    for name, run in (("plan", cmd_plan), ("dial", cmd_dial)):
        p = sub.add_parser(name, help="print the call" if name == "plan" else "place it")
        p.add_argument("--via", required=True, choices=VIA,
                       help="which rail rings: callheavy (this machine) or calle (hosted). there is no "
                            "default, because one of them spends credits")
        p.add_argument("--goal", required=True, help="what the call is for, in words")
        p.add_argument("--to", required=True, help="one recipient in e164")
        p.add_argument("--region", help="two letter country code, for the hosted rail only")
        p.add_argument("--schema", help="a json schema file: the fields to bring back")
        p.add_argument("--success", help="how either side would know it worked")
        p.add_argument("--notes", help="context the agent should have")
        p.add_argument("--language")
        p.add_argument("--socket", default=f"{host.CTRL_BIND}:{host.CTRL_PORT}")
        p.set_defaults(handler=run)

    dial_p = sub.choices["dial"]
    dial_p.add_argument("--authorized", help="who asked for this call")
    dial_p.add_argument("--run", action="store_true", help="actually dial")
    dial_p.add_argument("--settle", type=float, default=45.0, help="seconds to listen for the ending (callheavy)")
    dial_p.add_argument("--wait", type=float, default=600.0, help="seconds to wait for the hosted result (calle)")
    dial_p.add_argument("--no-wait", action="store_true", help="return the call id at once and read it later (calle)")

    for name, handler, what in (("status", cmd_status, "read one hosted call by id"),
                                ("cancel", cmd_cancel, "cancel one hosted call by id")):
        q = sub.add_parser(name, help=what)
        q.add_argument("--via", required=True, choices=VIA)
        q.add_argument("--id", required=True)
        q.set_defaults(handler=handler)

    mic_p = sub.add_parser("mic", help="the capture device, and what it costs")
    mic_p.add_argument("--wav", help="use a wav as a browser microphone instead of a device")
    mic_p.add_argument("--platform", choices=sorted(audio.MIC))
    mic_p.set_defaults(handler=cmd_mic)

    room_p = sub.add_parser("room", help="the livekit gate, and the bridge that is not shipped")
    room_p.set_defaults(handler=cmd_room)

    result_p = sub.add_parser("result", help="validate an extracted answer against its schema")
    result_p.add_argument("--schema", required=True)
    result_p.add_argument("--result", help="the extracted answer, as json")
    result_p.add_argument("--transcript", help="the call record this answer came from")
    result_p.set_defaults(handler=cmd_result)

    prompt_p = sub.add_parser("prompt", help="the question to ask our own model about a transcript")
    prompt_p.add_argument("--goal", required=True)
    prompt_p.add_argument("--schema", required=True)
    prompt_p.add_argument("--transcript", required=True)
    prompt_p.add_argument("--success")
    prompt_p.add_argument("--notes")
    prompt_p.add_argument("--language")
    prompt_p.set_defaults(handler=cmd_prompt)
    return parser


def main(argv=None):
    parser = build(argv)
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2
    answer, code = handler(args)
    print(json.dumps(answer, indent=2, sort_keys=True, default=str))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
