"""the inbox: what arrived while the machine was not listening.

jsonl on disk, one message per line, deduplicated by the provider's own id so a
retried webhook does not become two texts. this file is the reason a text can
outlive a powered-off guest: the catcher wrote it down.
"""
import json
import os
import time
from pathlib import Path


def default_path():
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "telephony" / "inbox.jsonl"


def _key(entry):
    return entry.get("id") or f"{entry.get('from')}|{entry.get('at')}|{entry.get('body')}"


def append(entry, path=None):
    """store one message. returns (stored, reason)."""
    path = Path(path or default_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = dict(entry)
    entry.setdefault("stored_at", int(time.time()))
    key = _key(entry)
    existing = { _key(e) for e in read(path) }
    if key in existing:
        return False, "duplicate"
    with path.open("a") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return True, "stored"


def read(path=None, since_days=None):
    path = Path(path or default_path())
    if not path.is_file():
        return []
    out = []
    cutoff = None if since_days is None else time.time() - since_days * 86400
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue  # a torn line is not worth failing an agent's read
        if cutoff is not None and float(e.get("at") or 0) < cutoff:
            continue
        out.append(e)
    return out


def count(path=None):
    return len(read(path))
