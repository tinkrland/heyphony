"""views: the inbox, the call log and the voicemail, shaped for something without eyes.

none of this is a dashboard. a terminal agent reads json and needs three things a
human's mail client gives it for free: a stable handle, a way to know what it has not
looked at yet, and a cheap way to read one item in full without loading the rest.

so every row is `{n, id, channel, from, at, unread, preview}` with `n` stable for the
session, `--show n` expands exactly one body, and `--mark-read n` writes the mark. the
read state lives in a sidecar because a provider webhook does not tell us whether the
agent looked, and pretending it does would be the lie that makes an inbox useless.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

from src.manage import inbox
from src.linphone import sip

PREVIEW = 64


def state_dir(home=None):
    """heyphony's own state, beside linphone's files but not inside them."""
    base = Path(home or os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "telephony"


def _marks_path(home=None):
    return state_dir(home) / "read-marks.json"


def marks(home=None):
    path = _marks_path(home)
    if not path.is_file():
        return set()
    try:
        return set(json.loads(path.read_text()).get("ids") or [])
    except ValueError:
        return set()


def mark_read(ids, home=None):
    path = _marks_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    current = marks(home) | {str(i) for i in ids}
    path.write_text(json.dumps({"ids": sorted(current)}, indent=2))
    return sorted(current)


def group_digits(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def attribute(sender, body=None, recipient=None):
    """the same ladder the group store uses, kept behind one function so the view cannot drift."""
    try:
        from src.manage import groups
        return groups.attribute_inbound(sender=sender, text=body, recipient=recipient)
    except Exception:
        return {"groups": [], "by": None, "certain": False}


def _groups_by_number():
    """number -> [{id, name, member}], read from the group store. an unreadable store is not a
    reason for the inbox to fail, so it degrades to no attribution rather than an exception."""
    try:
        from src.manage import groups
        buckets = {}
        for group in groups.load().get("groups", []):
            for member in group.get("members", []):
                buckets.setdefault(group_digits(member.get("number")), []).append(
                    {"id": group["id"], "name": group["name"], "member": member.get("name")})
        return buckets
    except Exception:
        return {}


def _rows(home=None, path=None):
    """provider texts first: they are the ones that arrive while the machine sleeps."""
    rows = []
    for entry in inbox.read(path):
        rows.append({
            "id": str(entry.get("id") or f"{entry.get('sender')}|{entry.get('at')}"),
            "channel": entry.get("channel") or "sms",
            "from": entry.get("sender"), "to": entry.get("recipient"),
            "at": entry.get("at"), "body": entry.get("body") or "",
            "thread": entry.get("thread") or entry.get("sender"),
            "raw": entry.get("raw"),
        })
    for entry in sip.messages(home=home, limit=200):
        rows.append({
            "id": f"sip:{entry.get('at')}:{str(entry.get('body'))[:16]}",
            "channel": "sip", "from": entry.get("from"), "to": entry.get("to"),
            "at": entry.get("at"), "body": entry.get("body") or "",
            "thread": entry.get("from") if entry.get("direction") == "incoming" else entry.get("to"),
            "raw": entry,
        })
    seen, out = set(), []
    for row in sorted(rows, key=lambda r: float(r.get("at") or 0), reverse=True):
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        out.append(row)
    return out


def messages(home=None, path=None, unread=False, since_days=None, thread=None,
             limit=20, show=None, do_mark=None):
    read_ids = marks(home)
    rows = _rows(home, path)
    if since_days is not None:
        import time
        cutoff = time.time() - since_days * 86400
        rows = [r for r in rows if float(r.get("at") or 0) >= cutoff]
    if thread:
        rows = [r for r in rows if str(r.get("thread")) == str(thread)]
    if do_mark:
        mark_read([rows[i - 1]["id"] for i in do_mark if 0 < i <= len(rows)], home)
        read_ids = marks(home)
    if unread:
        rows = [r for r in rows if r["id"] not in read_ids]
    total = len(rows)
    rows = rows[:limit]
    from src.manage.groups import ATTRIBUTION_MEANS

    view = []
    for i, row in enumerate(rows, 1):
        entry = {
            "n": i, "id": row["id"], "channel": row["channel"], "from": row["from"],
            "at": row["at"], "thread": row["thread"],
            "unread": row["id"] not in read_ids,
            "preview": (row["body"] or "").replace("\n", " ")[:PREVIEW],
        }
        # a reply names its group when it quotes the code, and is only inferred from membership when
        # it does not. either way the name is resolved here, not written into the stored message
        found = attribute(row["from"], row.get("body"), row.get("to"))
        if found["groups"]:
            entry["groups"] = found["groups"]
            entry["attributed_by"] = found["by"]
            entry["certain"] = found["certain"]
            entry["note"] = ("a member of this named group writing to your did directly. there is no "
                             "group thread, so this is their own text. "
                             + ATTRIBUTION_MEANS[found["by"]])
        view.append(entry)
    out = {"inbox": "messages", "count": total, "shown": len(view),
           "unread_total": sum(1 for r in _rows(home, path) if r["id"] not in read_ids),
           "rows": view,
           "hint": "open --show N for one body; --mark-read N to clear it; --unread to filter"}
    if show and 0 < show <= len(rows):
        out["message"] = {**rows[show - 1], "n": show}
    return out


def calls(home=None, missed=False, limit=20, show=None):
    rows = sip.calls(home=home, missed_only=missed, limit=limit)
    view = []
    for i, row in enumerate(rows, 1):
        view.append({"n": i, **row,
                     "who": row["caller"] if row["direction"] == "incoming" else row["callee"],
                     "when": row["started"],
                     "missed": row["status"] == "missed"})
    out = {"inbox": "calls", "count": len(view), "rows": view,
           "missed": sum(1 for r in view if r["missed"]),
           "hint": "open --show N for one call in full"}
    if show and 0 < show <= len(view):
        out["call"] = view[show - 1]
    return out


VOICE_EXT = (".wav", ".mp3", ".ogg", ".m4a", ".flac", ".opus")


def voicemail_dir(home=None):
    return Path(os.environ.get("HEYPHONY_VOICEMAIL_DIR") or state_dir(home) / "voicemail")


def voicemail(home=None, path=None, limit=20, show=None, play=None):
    """voicemail is a carrier feature, so this reads wherever the carrier put it:
    voip.ms emails it, flowroute does not answer at all, and a forwarded file lands here."""
    folder = Path(path) if path else voicemail_dir(home)
    rows = []
    if folder.is_dir():
        for item in sorted(folder.iterdir()):
            if item.suffix.lower() not in VOICE_EXT:
                continue
            sidecar = item.with_suffix(".json")
            meta = {}
            if sidecar.is_file():
                try:
                    meta = json.loads(sidecar.read_text())
                except ValueError:
                    meta = {}
            rows.append({"id": item.name, "file": str(item),
                         "from": meta.get("from") or meta.get("caller"),
                         "at": meta.get("at") or meta.get("received") or item.stat().st_mtime,
                         "seconds": meta.get("seconds") or meta.get("duration"),
                         "transcript": meta.get("transcript") or meta.get("text"),
                         "bytes": item.stat().st_size})
    rows.sort(key=lambda r: float(r.get("at") or 0), reverse=True)
    view = []
    for i, row in enumerate(rows[:limit], 1):
        view.append({"n": i, "id": row["id"], "from": row["from"], "at": row["at"],
                     "seconds": row["seconds"], "transcript": (row["transcript"] or "")[:PREVIEW],
                     "file": row["file"]})
    out = {"inbox": "voicemail", "dir": str(folder), "count": len(rows), "rows": view,
           "carrier_note": "voip.ms emails voicemail; flowroute does not answer. a provider that emails it arrives through the email lane, and this view reads what was put here.",
           "hint": "open --show N for the full transcript; --play N to hear it if a player exists"}
    if show and 0 < show <= len(rows):
        out["voicemail"] = rows[show - 1]
    if play and 0 < play <= len(rows):
        out["played"] = _play(Path(rows[play - 1]["file"]))
    return out


def _play(file):
    for player in (("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet"]), ("paplay", []), ("aplay", ["-q"])):
        binary = shutil.which(player[0])
        if binary:
            proc = subprocess.run([binary, *player[1], str(file)], capture_output=True, text=True)
            return {"player": player[0], "code": proc.returncode, "file": str(file),
                    "err": (proc.stderr or "").strip()[-200:]}
    return {"played": False, "why": "no player on this host (ffplay, paplay or aplay). the file path is still in the row"}
