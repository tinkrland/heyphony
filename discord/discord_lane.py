"""discord: watch, then answer only when addressed.

shaped after tinkrland/prixie.ai routes/discord.ts: the watcher is a singleton per
process and the token belongs to the server, not the request.
"""
import os

LANE = {
    "name": "discord", "folder": "discord",
    "carrier": "gateway websocket (watch) + rest api (reply)",
    "intake": "guild events, mentions, watched voice states",
    "relay": "bot message, only in a channel that addressed it",
    "gate": ("DISCORD_BOT_TOKEN",),
    "state": "designed",
    "evidence": "the watch contract is defined and the token gate is tested; no live gateway connection has run here",
}

WATCH_STATE = {"one_watcher_per_process": True, "token_from_env": True, "routes_read_only": True,
               "speaks_unprompted": False}


def watch_plan(guild_ids=None, env=None):
    env = env if env is not None else os.environ
    if not env.get("DISCORD_BOT_TOKEN"):
        return {"watching": False, "why": "DISCORD_BOT_TOKEN is unset, so the watch stays closed"}
    return {"watching": True, "guild_ids": guild_ids or [], "state": WATCH_STATE,
            "note": "a watched room opening a call is a signal to attend, not a place to talk"}


def reply_plan(channel_id, body, addressed=False, env=None):
    """a channel behaves like a group: no mention, no answer."""
    env = env if env is not None else os.environ
    if not env.get("DISCORD_BOT_TOKEN"):
        return {"sendable": False, "why": "bot token unset"}
    if not addressed:
        return {"sendable": False, "why": "not addressed: the agent answers people who asked it"}
    return {"sendable": True, "channel_id": channel_id, "body": body}
