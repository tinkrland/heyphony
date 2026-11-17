"""the four shapes of brain, as data, so the page and the argv cannot drift apart.

a brain is whatever answers when this number receives something. it is deliberately not part of
heyphony: the rails here are how a message arrives and how a reply leaves, and the thinking in
between is somebody else's product, already installed, already paid for, already theirs.

every row answers the same four questions: where the prompt goes, where the answer comes from,
what proves the brain is present, and what it never gets from us. the key rule is in `redact`: no
secret is ever placed on a command line, because a command line is readable by every process on
the machine, and a brain that needs a key gets it in the environment or not at all.
"""
import os
import shlex

ADAPTERS = {
    "claude": {
        "name": "claude",
        "what": "claude code, the cli a person already has",
        "kind": "cli",
        "binary": "claude",
        "argv": ["claude", "-p"],
        "prompt": "argv",
        "answer": "stdout",
        "auth": "its own login: this branch never sees the token",
        "needs": [],
        "note": "the prompt rides argv, so it is visible in `ps` for as long as the turn runs; "
                "that is a transcript of somebody's text, not a secret, and the note is here "
                "rather than discovered later",
        "evidence": "the cli documents -p for one-shot answers; no turn has been run from here",
    },
    "codex": {
        "name": "codex",
        "what": "openai's codex cli, in its non-interactive exec mode",
        "kind": "cli",
        "binary": "codex",
        "argv": ["codex", "exec"],
        "prompt": "argv",
        "answer": "stdout",
        "auth": "its own login",
        "needs": [],
        "note": "exec is the one-shot verb; the interactive tui is never driven from a script",
        "evidence": "the cli documents exec for non-interactive use; no turn has been run from here",
    },
    "openai": {
        "name": "openai",
        "what": "any endpoint that speaks the chat completions shape",
        "kind": "http",
        "base": "OPENAI_BASE_URL",
        "path": "/chat/completions",
        "prompt": "json",
        "default_base": "https://api.openai.com/v1",
        "model_env": "HEYPHONY_BRAIN_MODEL",
        "default_model": "gpt-4o-mini",
        "auth": "OPENAI_API_KEY, read from the environment and sent as a bearer header",
        "needs": ["OPENAI_API_KEY"],
        "note": "the base url is an env var because a compatible endpoint is the point: a local "
                "server, a proxy, or the vendor",
        "evidence": "chat completions is the documented shape; no request has left this branch",
    },
    "shell": {
        "name": "shell",
        "what": "any command that reads a prompt on stdin and writes an answer on stdout",
        "kind": "cli",
        "binary": "HEYPHONY_BRAIN_CMD",
        "argv": [],
        "prompt": "stdin",
        "answer": "stdout",
        "auth": "whatever that command already has",
        "needs": ["HEYPHONY_BRAIN_CMD"],
        "note": "the escape hatch, and the only one whose prompt never touches argv",
        "evidence": "stdio is the oldest contract there is; no command has been run from here",
    },
}

# what a brain is never asked to do from here. these are refusals rather than missing features:
# each one is a thing that looks convenient and moves a human decision into a model.
REFUSED = [
    "answer a call as the person who owns the number, without saying what it is",
    "send without the gate: a brain drafts, and a human opens the gate",
    "hold a key: the key lives in the environment of the turn, never on the command line",
    "remember across turns by default: a number is not a memory, and this branch keeps no store",
]

SECRET_ENVS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "HEYPHONY_BRAIN_KEY")


def known():
    return sorted(ADAPTERS)


def get(name):
    if name not in ADAPTERS:
        raise KeyError(f"unknown brain: {name}; known: {', '.join(known())}")
    return ADAPTERS[name]


def missing(name, env=None):
    """what this brain needs from a person before a turn can run at all."""
    env = env if env is not None else {}
    row = get(name)
    gaps = [key for key in row.get("needs", []) if not env.get(key)]
    if row["kind"] == "cli" and row["binary"] != "HEYPHONY_BRAIN_CMD":
        if not which(row["binary"], env):
            gaps.append(row["binary"])
    return gaps


def which(binary, env=None):
    """found and executable, asked of PATH rather than assumed: a brain that is not installed
    should say so before a text is spent on it."""
    env = env if env is not None else {}
    path = env.get("PATH", "")
    for folder in path.split(":"):
        if not folder:
            continue
        candidate = f"{folder.rstrip('/')}/{binary}"
        if candidate and _executable(candidate):
            return candidate
    return None


def _executable(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)


def command(name, prompt, env=None):
    """the argv to run, the text to write to its stdin, and nothing secret on the command line."""
    env = env if env is not None else {}
    row = get(name)
    if row["kind"] == "http":
        return None, None
    if name == "shell":
        custom = env.get("HEYPHONY_BRAIN_CMD", "").strip()
        if not custom:
            raise KeyError("shell needs HEYPHONY_BRAIN_CMD: a command that reads stdin")
        # shlex, not split: a command a person writes has quotes in it, and a naive split turns
        # `python3 -c "print(1)"` into four arguments and a syntax error
        argv = shlex.split(custom)
        return argv, prompt
    argv = list(row["argv"])
    if row["prompt"] == "argv":
        argv.append(prompt)
    return argv, (prompt if row["prompt"] == "stdin" else None)


def redact(argv, env=None):
    """the same argv with anything that looks like a credential replaced, because this line gets
    printed into logs and into a transcript a person reads."""
    env = env if env is not None else {}
    secrets = [env[k] for k in SECRET_ENVS if env.get(k)]
    clean = []
    for word in argv or []:
        for secret in secrets:
            if secret and secret in word:
                word = word.replace(secret, "<redacted>")
        clean.append(word)
    return clean


def means():
    return ("a brain receives one prompt per arrival and answers with text; whether that text is "
            "sent, drafted or dropped is this branch's decision, never the brain's")
