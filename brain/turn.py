"""one arrival, one turn: what the brain is asked, and what this branch does with the answer.

the whole branch is this file. a text has already arrived and is already stored, because the inbox
on `mcp` does that without asking anyone. the turn reads that stored envelope, asks the brain one
question about it, and then makes a decision that is not the brain's to make: send, draft, or drop.

the gate is the same one every other spending path in this package uses. a shut gate still costs a
model call if a person asked for a turn, so the turn says so before it runs: the draft is the
default, and HEYPHONY_SEND=allowed is a person deciding that a text may leave.
"""
import json

from brain import adapters, compat

HEAD = ("you are the person whose phone number received the message below. answer it as that "
        "person would: one short message, no greeting template, no signature, no mention of being "
        "an assistant. if the message needs no answer, reply with the single word DROP.")


def event(row):
    """the stored envelope, reduced to the four things a brain may see. `raw` stays behind: it is
    the carrier's payload, and a brain answering a text does not need the header soup."""
    return {"from": row.get("sender"), "at": row.get("at"), "body": row.get("body"),
            "channel": row.get("channel"), "id": row.get("id")}


def prompt_for(row):
    """two lines: standing instruction, then the message. no history, because this branch keeps
    none, and no tool list, because the brain is answering a text rather than operating a machine."""
    one = event(row)
    body = (one.get("body") or "").strip() or "(empty message)"
    return {"system": HEAD,
            "user": "from: {}\nat: {}\nchannel: {}\n\n{}".format(
                one.get("from") or "unknown", one.get("at") or "unknown",
                one.get("channel") or "sms", body)}


def decide(answer, env, to):
    """the branch's decision, not the model's. DROP is the model declining; a shut gate and a
    missing recipient are ours."""
    env = env if env is not None else {}
    text = (answer or "").strip()
    if not text or text.upper().strip(".") == "DROP":
        return {"action": "drop", "why": "the brain declined, and a declined text is not sent"}
    if not to:
        return {"action": "drop", "text": text,
                "why": "no recipient: the reply has nowhere to go without --to"}
    if env.get("HEYPHONY_SEND") != "allowed":
        return {"action": "draft", "text": text, "to": to,
                "why": "the send gate is shut, so this is a draft: HEYPHONY_SEND=allowed sends it"}
    return {"action": "send", "text": text, "to": to,
            "argv": ["send", "--text", text, "--to", to, "--send"],
            "why": "the gate is open and a person opened it"}


def ask(name, prompt, env, opener=None):
    """one question to one brain, whichever shape it is."""
    row = adapters.get(name)
    gaps = adapters.missing(name, env)
    if gaps:
        return False, {"missing": gaps,
                       "why": "this brain is not ready: what is missing is listed, and none of it "
                              "is guessed at"}
    if row["kind"] == "http":
        ok, said = compat.ask(row, prompt, env, opener=opener)
        return ok, said
    argv, stdin = adapters.command(name, prompt["user"] if row.get("prompt") == "stdin" else _flat(prompt),
                                   env)
    return True, {"argv": adapters.redact(argv, env), "stdin": bool(stdin),
                  "means": "the command is built and not run here: `run` is the verb that spends"}


def _flat(prompt):
    return prompt["system"] + "\n\n" + prompt["user"]


def one_turn(name, row, env, to, runner=None, opener=None):
    """a whole turn, with the runner injected so the decision can be tested without a model.

    runner(argv, stdin_text) -> (ok, text) is the only thing that touches a brain, and it is a
    parameter rather than an import, because a suite that calls a model is a suite that fails on a
    train.
    """
    prompt = prompt_for(row)
    gaps = adapters.missing(name, env)
    if gaps:
        return {"ok": False, "brain": name, "missing": gaps,
                "why": "this brain is not ready: nothing was asked and nothing was spent"}
    spec = adapters.get(name)
    said = {"brain": name, "event": event(row), "prompt": prompt, "sent": False}

    if spec["kind"] == "http":
        ok, answer = compat.ask(spec, prompt, env, opener=opener)
        said["asked"] = True
    else:
        argv, stdin = adapters.command(name, prompt["user"] if spec.get("prompt") == "stdin" else _flat(prompt),
                                       env)
        said["argv"] = adapters.redact(argv, env)
        said["asked"] = True
        if runner is None:
            said["decision"] = {"action": "drop",
                                "why": "no runner: a turn without one builds the command and stops"}
            said["ok"] = True
            return said
        ok, answer = runner(argv, stdin)

    if not ok:
        said["ok"] = False
        said["why"] = answer
        return said

    decision = decide(answer, env, to)
    said["ok"] = True
    said["answer"] = answer
    said["decision"] = decision
    if decision["action"] == "send":
        said["sent"] = True
    return said


def errored(text):
    """a brain that answered with an error is a brain that answered, and the turn says which."""
    try:
        json.loads(text)
        return None
    except (TypeError, ValueError):
        return None
