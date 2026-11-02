"""linphone, read from its own source rather than guessed.

what was checked in BelledonneCommunications/linphone-sdk (master, 2026-11-01):

- account settings live in sections named ``proxy_%i`` (account/account.cpp) and
  carry ``reg_proxy``, ``reg_identity``, ``reg_expires``, ``realm``
  (account/account-params.cpp)
- credentials live in ``auth_info_%i`` and carry ``username``, ``userid``,
  ``passwd``, ``realm``, ``domain``, ``ha1`` (auth-info/auth-info.cpp)
- call history is a sqlite table ``call_history`` with id, caller, callee,
  direction, duration, start_time, connected_time, status, videoEnabled,
  quality, call_id, refkey (tester/db/call-history.db)
- sip messages are in a sqlite table ``history`` with id, localContact,
  remoteContact, direction, message, time, read, status, url, utc, appdata,
  content, messageId, content_type, is_secured (tester/db/messages.db)

the rc keys are real. the value formats below (sip: uris) are conventional, and
the data directory names follow linphone's own conventions: a first live run is
what proves the paths on a given distro.
"""
import os
import sqlite3
from pathlib import Path

DIRECTIONS = {0: "outgoing", 1: "incoming"}
CALL_STATUS = {0: "success", 1: "aborted", 2: "missed", 3: "declined", 4: "early-aborted"}
DB_NAMES = {"calls": "call-history.db", "messages": "messages.db"}


def config_dir(home=None):
    home = Path(home or os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return home / "linphone"


def data_dir(home=None):
    home = Path(home or os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return home / "linphone"


def rc_path(home=None):
    return config_dir(home) / "linphonerc"


def sip_host(provider, server=None):
    """the registration host. voip.ms is regional, so a wrong server is the
    classic silent failure; flowroute publishes its own."""
    if server:
        return server
    return {"voip.ms": "atlanta.voip.ms", "flowroute": "sip.flowroute.com"}[provider.lower()]


def rc_text(provider, did, username, password, server=None):
    host = sip_host(provider, server)
    ident = f"sip:{username}@{host}"
    return "\n".join([
        "[sip]",
        "sip_port=5060",
        "",
        "[proxy_0]",
        f"reg_proxy=sip:{host};transport=tls",
        f"reg_identity={ident}",
        "reg_expires=3600",
        f"realm={host}",
        "",
        "[auth_info_0]",
        f"username={username}",
        f"userid={username}",
        f"passwd={password}",
        f"realm={host}",
        f"domain=sip:{host}",
        "",
        "[telephony]",
        f"provider={provider.lower()}",
        f"did={did}",
        "",
    ])


def write_rc(provider, did, username, password, server=None, home=None):
    path = rc_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rc_text(provider, did, username, password, server))
    os.chmod(path, 0o600)  # it holds a password
    return path


def read_rc(path=None):
    """the section map of an rc file, without needing configparser quirks
    (linphone writes duplicate-ish keys and comment styles)."""
    path = Path(path or rc_path())
    out, section = {}, "root"
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            out[section] = {}
        elif "=" in line and not line.startswith(("#", ";")):
            k, v = line.split("=", 1)
            out[section][k.strip()] = v.strip()
    return out


ENDPOINTS = ("host", "guest")

# which host-side client actually drives the line. decided, not deferred.
HOST_CLIENTS = {
    "baresip": {
        "chosen": True,
        "why": "its ctrl_tcp module is a json command socket: newline json in, json out, "
               "with \"command\": \"dial\" and an event bus back. read from the module source "
               "(json_decode_odict, ctrl_tcp_listen 0.0.0.0:4444 in the shipped config example). "
               "a small c binary, plain-text config, one process per line.",
        "weight": "small: static-ish c, no heavy media stack, modules load on demand",
        "cost": "the config is its own dialect, so heyphony writes it rather than documenting it",
    },
    "pjsua": {
        "chosen": False,
        "why": "scriptable through pjsua2 python bindings, which is genuinely nice, but it drags the "
               "whole pjsip media stack along and the interactive console is a telnet cli instead of a "
               "typed protocol. more surface to bind, more to break on a quiet host.",
        "weight": "heavier: pjsip + pjmedia + pjlib, and python bindings built per host",
        "cost": "a python abi per host, for a lane that mostly needs to dial and hang up",
    },
}


def host_client():
    """the one decision this lane was missing, with the reason attached."""
    return {"client": "baresip", "control": "json over tcp (ctrl_tcp)",
            "transport": "sip/rtp", "alternatives": HOST_CLIENTS}


def connection_plan(did, endpoint="host"):
    """where the number actually registers, which is not where the agent runs.

    a did is one registration, and the machine that holds it does not have to be
    the machine that answers a given message. the default is the durable host for
    three reasons that all point the same way: the sip password is a long-lived
    secret and a throwaway guest burns one per spawn, one number means one
    registration rather than a race between machines, and a number that rings
    while no guest is running is the whole point of having a number.
    """
    if endpoint not in ENDPOINTS:
        raise KeyError(f"unknown endpoint: {endpoint}")
    on_host = endpoint == "host"
    return {
        "did": did,
        "endpoint": endpoint,
        "registrations": 1,
        "secret_location": "the host's config dir, 0600" if on_host else "inside the burnable machine",
        "secret_in_burn": not on_host,
        "survives_burn": on_host,
        "rings_with_no_guest": on_host,
        "rotation": "once, on the host" if on_host else "every spawn, per machine",
        "guests_read": "the inbox over the control plane" if on_host else "the local database only",
        "verdict": "default" if on_host else "allowed, but you are putting a long-lived credential in a machine you intend to shred",
    }


def find_db(kind, home=None):
    p = data_dir(home) / DB_NAMES[kind]
    return p if p.is_file() else None


def calls(home=None, db=None, missed_only=False, limit=50):
    target = Path(db) if db else find_db("calls", home)
    if not target or not Path(target).is_file():
        return []
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    sql = "select caller, callee, direction, duration, start_time, status, call_id from call_history"
    if missed_only:
        sql += " where status = 2"
    sql += " order by start_time desc limit ?"
    rows = conn.execute(sql, (limit,)).fetchall()
    conn.close()
    return [{"caller": r[0], "callee": r[1], "direction": DIRECTIONS.get(r[2], r[2]),
             "duration_s": r[3], "started": r[4], "status": CALL_STATUS.get(r[5], r[5]),
             "call_id": r[6]} for r in rows]


def messages(home=None, db=None, limit=50):
    """sip messages only. on a pstn did this table is usually empty, which is
    the truth and not a bug: texts arrive at the provider, not in the phone."""
    target = Path(db) if db else find_db("messages", home)
    if not target or not Path(target).is_file():
        return []
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    rows = conn.execute(
        "select remoteContact, localContact, direction, message, time, read, status "
        "from history order by time desc limit ?", (limit,)).fetchall()
    conn.close()
    return [{"from": r[0], "to": r[1], "direction": DIRECTIONS.get(r[2], r[2]),
             "body": r[3], "at": r[4], "read": bool(r[5]), "status": r[6]} for r in rows]
