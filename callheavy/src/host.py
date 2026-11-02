"""the host: the two files baresip reads, written so a process can drive the call.

this is our own call setup, and it lives here rather than in the package because the package's job is
the number rather than the call control. the keys below are read out of baresip's own shipped example
(`docs/examples/config`) rather than from memory, and two of them are the reason this file exists:

- `ctrl_tcp.so` is present in that example and **commented out**, so a host that never uncomments it
  has no json socket at all, and nothing says so until a client tries to connect.
- the call commands (`dial`, `hangup`, `answer`) are not core commands: they are registered by the
  `menu` module. so the socket without `menu.so` is a socket that refuses every verb worth having.

both are written explicitly here, and both are pinned by a test, because they fail the same way: a
connection that opens, answers nothing, and looks like the client's bug.
"""
import os
import pathlib

CTRL_PORT = 4444
CTRL_BIND = "127.0.0.1"

# one row per host, because the audio driver is the one line that is never portable. `verified` is
# honest: only the linux row has been run here, and the others say so rather than implying otherwise.
HOSTS = {
    "linux": {"module": "alsa.so", "device": "alsa,default", "verified": True,
              "note": "alsa is the example config's default; pipewire speaks alsa through its pulse bridge"},
    "macos": {"module": "coreaudio.so", "device": "coreaudio,default", "verified": False,
              "note": "coreaudio ships with brew's baresip; the first thing to check on real hardware"},
    "windows": {"module": "wasapi.dll", "device": "wasapi,default", "verified": False,
                "note": "wasapi is the windows driver, and windows needs wsl2 for the cli to run at all"},
}

# modules, and what breaks when one is missing. this is the part that saves the afternoon.
MODULES = (
    ("stdio.so", "the console, which is how a failure gets a log line instead of a silence"),
    ("g711.so", "a codec both ends agree on; without one the call connects and nobody hears anything"),
    ("account.so", "loads accounts from the accounts file"),
    ("audio.so", "the host's audio driver, substituted below: the one line that is never portable"),
    ("menu.so", "registers dial, hangup and answer. ctrl_tcp does not provide them"),
    ("ctrl_tcp.so", "the json socket this lane drives. commented out in the shipped example"),
    ("stun.so", "nat traversal, so a call survives a home router"),
)

ACCOUNTS_TEMPLATE = (
    '# one line: <display> <sip:user@host>;auth_user=..;auth_pass=..;regint=..\n'
    '"{name}" <sip:{user}@{host}>;auth_user={user};auth_pass={password};regint={regint}\n'
)


def host_row(platform=None):
    name = platform or ("macos" if os.uname().sysname == "Darwin" else "linux")
    return dict(HOSTS.get(name, HOSTS["linux"]), platform=name)


def module_path():
    """baresip's default install location, settable because a distro will disagree."""
    return os.environ.get("HEYPHONY_BARESIP_MODULES") or "/usr/lib/baresip/modules"


def config_text(platform=None, port=CTRL_PORT, bind=CTRL_BIND, module_path_=None):
    """the config, with the control socket on loopback rather than on every interface."""
    row = host_row(platform)
    lines = [
        "# written by callheavy. baresip's own keys, and one comment per module saying what it is for.",
        f"module_path\t\t{module_path_ or module_path()}",
        "",
        "# the registration and the rtp socket",
        "sip_listen\t\t0.0.0.0:5060",
        "call_max_calls\t\t2",
        "",
        f"# audio: {row['note']}",
        f"audio_player\t\t{row['device']}",
        f"audio_source\t\t{row['device']}",
        f"audio_alert\t\t{row['device']}",
        "ausrc_format\t\ts16",
        "auplay_format\t\ts16",
        "",
        "# the json socket. loopback only: a socket that can dial and hang up is not a lan service.",
        f"ctrl_tcp_listen\t\t{bind}:{port}",
        "",
    ]
    for module, why in MODULES:
        driver = row["module"] if module == "audio.so" else module
        lines.append(f"module\t\t\t{driver}\t# {why}")
    return "\n".join(lines) + "\n"


def accounts_text(did, username, password, host, display=None, regint=3600):
    """the accounts file. one line, and the password is why it is written 0600."""
    if not host or "/" in host or " " in host:
        raise ValueError("the sip host has to be a hostname, not a server description")
    return ACCOUNTS_TEMPLATE.format(name=display or did, user=username, host=host,
                                    password=password, regint=regint)


def paths(home=None):
    base = pathlib.Path(home or os.environ.get("HEYPHONY_BARESIP_DIR") or pathlib.Path.home() / ".baresip")
    return {"config": base / "config", "accounts": base / "accounts"}


def write(did, username, password, host, home=None, platform=None, port=CTRL_PORT, bind=CTRL_BIND,
          dry=False):
    """write both files, both 0600. a dry run returns the text so it can be read before it is trusted."""
    where = paths(home)
    config = config_text(platform=platform, port=port, bind=bind)
    accounts = accounts_text(did, username, password, host, display=did)
    if dry:
        return {"ok": True, "dry": True, "config": config, "accounts": accounts,
                "ctrl": f"{bind}:{port}",
                "paths": {key: str(value) for key, value in where.items()}}
    where["config"].parent.mkdir(parents=True, exist_ok=True)
    for key in ("config", "accounts"):
        target = where[key]
        target.write_text(config if key == "config" else accounts)
        os.chmod(target, 0o600)
    return {"ok": True, "dry": False, "ctrl": f"{bind}:{port}",
            "paths": {key: str(value) for key, value in where.items()},
            "next": "start baresip, then: callheavy dial --to +1555... --goal '...'"}


def loaded_modules(text):
    """what a written config actually loads, read out of the file rather than assumed from the intent."""
    found = []
    for line in text.splitlines():
        tokens = line.split("#")[0].split()
        if len(tokens) >= 2 and tokens[0] == "module":
            found.append(tokens[1])
    return found
