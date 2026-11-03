"""streaming: twitch and kick. the lane that publishes, on a human's press only."""
import os

PLATFORMS = {
    "twitch": {"ingest": "rtmp/rtmps with a stream key", "api": "official helix",
               "gate": ("TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET"), "state": "designed"},
    "kick": {"ingest": "rtmp with a stream key", "api": "unofficial, so no api calls from here",
             "gate": ("KICK_STREAM_KEY",), "state": "designed"},
}

LANE = {
    "name": "streaming", "folder": "streaming",
    "carrier": "rtmp ingest, obs for scenes",
    "intake": "chat, if the platform's api allows reading it",
    "relay": "the stream itself: the one lane that publishes",
    "gate": ("TWITCH_CLIENT_ID", "KICK_STREAM_KEY"),
    "state": "designed",
    "evidence": "ingest paths named per platform; nothing has streamed",
}


def go_live_plan(platform, env=None):
    """builds the plan, never the stream. the last step is a person."""
    env = env if env is not None else os.environ
    if platform not in PLATFORMS:
        return {"live_ready": False, "why": f"platform not modelled: {platform}"}
    spec = PLATFORMS[platform]
    missing = [g for g in spec["gate"] if not env.get(g)]
    plan = {"platform": platform, "ingest": spec["ingest"], "api": spec["api"],
            "live_ready": not missing, "missing": missing,
            "human_presses_go_live": True,
            "publishes": True,
            "why_the_rule_flips": "every other lane renders and hands back. a stream is the output, so the press is a person's, which is also how a mistake stays recoverable."}
    if platform == "kick" and not missing:
        plan["refuses"] = "kick has no official api: title and category are set in a browser, not by us"
    return plan
