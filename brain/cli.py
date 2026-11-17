"""the verb surface: four questions a person asks about a brain, and the one that spends.

`adapters` answers what this host could run. `plan` answers what a turn would say and cost without
saying it. `hello` spends exactly one call to prove the brain answers at all. `run` is the turn.

the ordering is the point, and it is the same ladder the rest of this package climbs: read first,
then plan, then one cheap proof, then the real thing.
"""
import argparse
import json
import os
import subprocess
import sys

from brain import adapters, compat, turn

VERBS = ("adapters", "plan", "hello", "run", "refused")


def out(payload):
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def read_row(args):
    """one stored envelope, by id from the inbox on `mcp`, or from a file when there is no inbox:
    the file route is how a machine with no number can still be asked what it would say."""
    if getattr(args, "file", None):
        with open(args.file) as handle:
            return json.load(handle)
    from src.manage import inbox
    rows = inbox.read()
    for row in rows:
        if row.get("id") == args.id:
            return row
    raise SystemExit(f"no stored message with id {args.id}; {len(rows)} messages are here")


def cmd_adapters(args):
    env = os.environ
    return out({"adapters": {name: {"what": row["what"], "kind": row["kind"],
                                    "auth": row["auth"], "prompt": row.get("prompt"),
                                    "missing": adapters.missing(name, env), "evidence": row["evidence"]}
                             for name, row in adapters.ADAPTERS.items()},
                "means": adapters.means(),
                "rule": "no key is placed on a command line: a brain reads its own environment"})


def cmd_plan(args):
    row = read_row(args)
    prompt = turn.prompt_for(row)
    spec = adapters.get(args.brain)
    said = {"brain": args.brain, "event": turn.event(row), "prompt": prompt,
            "missing": adapters.missing(args.brain, os.environ),
            "spends": "one brain call per arrival, never a message unless the gate is open"}
    if spec["kind"] == "http":
        said["request"] = compat.plan(spec, prompt, os.environ)
    else:
        argv, stdin = adapters.command(args.brain, _prompt_for_cli(spec, prompt), os.environ)
        said["argv"] = adapters.redact(argv, os.environ)
        said["stdin"] = bool(stdin)
    said["decision_now"] = turn.decide("(the answer)", os.environ, getattr(args, "to", None))
    return out(said)


def _prompt_for_cli(spec, prompt):
    return prompt["user"] if spec["prompt"] == "stdin" else prompt["system"] + "\n\n" + prompt["user"]


def cmd_hello(args):
    """one question with a known answer, so 'the cli is installed' and 'the endpoint answers' are
    two different facts rather than one hope."""
    prompt = {"system": "you are a reachability check. obey the one instruction exactly.",
              "user": "reply with the single word READY and nothing else."}
    spec = adapters.get(args.brain)
    gaps = adapters.missing(args.brain, os.environ)
    if gaps:
        return out({"ok": False, "brain": args.brain, "missing": gaps,
                    "why": "nothing was asked: this brain is not ready on this host"})
    if spec["kind"] == "http":
        ok, answer = compat.ask(spec, prompt, os.environ)
    else:
        argv, stdin = adapters.command(args.brain, _prompt_for_cli(spec, prompt), os.environ)
        ok, answer = _run(argv, stdin)
    return out({"ok": bool(ok) and "READY" in str(answer).upper(), "brain": args.brain,
                "answer": answer if ok else None, "why": None if ok else answer,
                "means": "one call was spent: this proves reachability, not judgement"})


def _run(argv, stdin_text, timeout=120):
    """the only place a brain is executed. the prompt goes through a pipe when the adapter asks
    for stdin, so the run never needs a shell and never re-parses a message as arguments."""
    try:
        done = subprocess.run(argv, input=stdin_text, capture_output=True, text=True,
                              timeout=timeout)
    except FileNotFoundError:
        return False, f"{argv[0]} is not on PATH"
    except subprocess.TimeoutExpired:
        return False, f"the brain did not answer within {timeout}s"
    if done.returncode != 0:
        return False, (done.stderr or done.stdout or f"exit {done.returncode}").strip()[:300]
    return True, (done.stdout or "").strip()


def cmd_run(args):
    row = read_row(args)
    said = turn.one_turn(args.brain, row, os.environ, getattr(args, "to", None), runner=_run)
    if said.get("decision", {}).get("action") == "send" and said.get("sent"):
        argv = said["decision"].pop("argv")
        said["send"] = {"argv": argv, "ran": False,
                        "why": "the reply is sent by the number's own rail, which lives on `mcp`: "
                               "this branch decides and does not dial"}
    return out(said)


def cmd_refused(args):
    return out({"refused": adapters.REFUSED,
                "means": "each one is a human decision that would move into a model if it were allowed"})


def build_parser():
    p = argparse.ArgumentParser(prog="brain",
                               description="point your own agent at this number's rails")
    sub = p.add_subparsers(dest="verb")

    a = sub.add_parser("adapters", help="what this host could run, and what each one needs")
    a.set_defaults(func=cmd_adapters)

    pl = sub.add_parser("plan", help="what a turn would say and cost, without saying it")
    pl.add_argument("--brain", required=True, choices=adapters.known())
    pl.add_argument("--id")
    pl.add_argument("--file")
    pl.add_argument("--to")
    pl.set_defaults(func=cmd_plan)

    h = sub.add_parser("hello", help="one call, to prove the brain answers")
    h.add_argument("--brain", required=True, choices=adapters.known())
    h.set_defaults(func=cmd_hello)

    r = sub.add_parser("run", help="one turn: ask the brain, then draft or send")
    r.add_argument("--brain", required=True, choices=adapters.known())
    r.add_argument("--id")
    r.add_argument("--file")
    r.add_argument("--to")
    r.set_defaults(func=cmd_run)

    f = sub.add_parser("refused", help="what this branch will not ask a brain to do")
    f.set_defaults(func=cmd_refused)
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    if not getattr(args, "func", None):
        build_parser().print_help()
        return 2
    try:
        return args.func(args) or 0
    except KeyError as exc:
        out({"ok": False, "why": str(exc).strip("'\"")})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
