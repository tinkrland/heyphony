"""ring: the host sees the call before the agent does, and tells it in time to pick up.

the phone-rings-itself route is unreliable for the reasons the wake table already gives, and it does
not matter here: the number is registered on the host, the host is the thing that receives the invite,
and a host that is running can always see a call. so ringing is observable.

what is not free is the race. a caller gives up in thirty seconds or so, and most channels an idle
agent can be reached on are minutes. that single fact decides the policy: the host answers first and
tells the agent at the same time, rather than asking first and hoping the answer beats the caller.
"tell then answer" is a policy this file supports, and it is only honest on a channel that delivers in
seconds, which is why the table says which channels those are.
"""
import json
import os
import socket
import time

# what the host can observe, from baresip's own event bus over ctrl_tcp
RING_EVENTS = {
    "CALL_INCOMING": {
        "when": "an invite has arrived and nothing has answered it yet",
        "what_the_agent_gets": "the peer uri, and that a decision is wanted now",
        "matters": "this is the only event a pickup can be built on: it is the one that arrives while "
                   "the call is still ringable",
    },
    "CALL_RINGING": {
        "when": "the far end is being alerted",
        "what_the_agent_gets": "confirmation that the invite became ringtone rather than an error",
        "matters": "useful for outbound. for inbound the interesting event has already happened",
    },
    "CALL_ESTABLISHED": {
        "when": "media is connected, either because we answered or because the far end did",
        "what_the_agent_gets": "the moment the agent's voice is now audible to a person",
        "matters": "everything after this is a conversation rather than a notification",
    },
    "CALL_CLOSED": {
        "when": "the caller hung up, we declined, or the ring timed out",
        "what_the_agent_gets": "why, and how long it rang",
        "matters": "the event that tells a late agent the decision it was asked for has expired",
    },
}

# the channels an idle agent can be reached on, and the honest latency of each
NOTIFY = {
    "catcher": {
        "what": "a queue on a host that is always up, which the agent drains when it wakes",
        "reaches_a_sleeping_vm": True,
        "latency": "the agent's next poll",
        "needs": ["something always up to hold the queue, which is the same host that holds the line"],
        "cost": "a small service and a durable file",
        "verdict": "the reliable one, and the one that loses the thirty second race by design",
    },
    "email": {
        "what": "a message to the agent's own inbox",
        "reaches_a_sleeping_vm": True,
        "latency": "seconds to minutes, and then whatever the agent's poll interval is",
        "needs": ["the mail lane, which heyphony already has"],
        "cost": "nothing beyond the lane",
        "verdict": "good for the record and for reading later, too slow to decide a live call",
    },
    "sms": {
        "what": "a text to the did that is already answering",
        "reaches_a_sleeping_vm": True,
        "latency": "seconds",
        "needs": ["sms on the did, which is provider dependent"],
        "cost": "per message",
        "verdict": "push-shaped without an app. still usually slower than a caller",
    },
    "push": {
        "what": "apns or fcm to an app on a phone we own",
        "reaches_a_sleeping_vm": True,
        "latency": "a second or two when it works",
        "needs": ["an app, a signing identity and a push entitlement, which this branch does not have"],
        "cost": "an app to build and keep running",
        "verdict": "the only channel fast enough to decide the call, and it costs a client",
    },
    "webhook": {
        "what": "an http post to an endpoint we host",
        "reaches_a_sleeping_vm": False,
        "latency": "instant, to a receiver that has to be up",
        "needs": ["a receiver that is not the sleeping vm"],
        "cost": "the receiver",
        "verdict": "a transport, not a channel. useful when the catcher speaks http",
    },
    "file": {
        "what": "a line appended to a local log",
        "reaches_a_sleeping_vm": False,
        "latency": "zero, on the machine that is awake",
        "needs": [],
        "cost": "none",
        "verdict": "for tests and for a desk with a tail -f on it",
    },
}

# two ways to answer, and only one of them survives a slow channel
PICKUP = {
    "answer-then-tell": {
        "what": "the host answers at once, the notification goes out in the same breath, and the agent "
                "takes over the conversation or takes a message",
        "who_holds_media": "the host, which is the shape whose audio path this branch proved",
        "beats_the_race": True,
        "costs": ("the caller hears the agent's line before the agent has chosen anything, so that line "
                  "has to be true on its own"),
        "state": "recommended",
    },
    "tell-then-answer": {
        "what": "the host notifies, waits for the agent's answer command, and rings out if none comes",
        "who_holds_media": "the host, if the agent answers in time",
        "beats_the_race": False,
        "costs": ("only honest on a channel that delivers in seconds. on email the caller hears ringing "
                  "and then voicemail, and the notification arrives about a call that is already over"),
        "state": "designed",
    },
}

# the budget a live call imposes, and what happens past it
RING_BUDGET = {
    "caller_patience_s": (25, 45),
    "decide_by_s": 20,
    "past_it": ("the carrier's own voicemail, or the forwarding rows that survive a sleeping host. a "
                "notification that arrives after the ring is a record, not an invitation"),
}

REFUSED = {
    "answer-blind": ("answering without the line saying what it is. the first turn of every call names the "
                     "agent, and a confused silence is not a greeting"),
    "notify-as-the-plan": ("treating a notification as the plan for pickup. email is minutes and a caller "
                           "is thirty seconds, so the plan is answer-then-tell and the notification is the "
                           "second half of it"),
    "wake-the-phone-to-answer": ("waking a handset so it can answer. the media lands in its earpiece and "
                                 "the agent still hears nothing, which is the row this branch already "
                                 "refuses"),
    "silent-listener": ("listening to a line without saying so. the listener here is the same host that "
                        "answers, and the caller is told what answered"),
    "retry-the-ring": ("calling a caller back because the notification was late, without saying it is a "
                       "machine doing the calling back"),
}


def ring_plan(channel="catcher"):
    """the ordered steps, with the race named at the point where it bites."""
    if channel not in NOTIFY:
        raise KeyError(f"no such channel: {channel}. the ones that exist are {sorted(NOTIFY)}")
    return {
        "channel": channel,
        "policy": "answer-then-tell",
        "steps": [
            {"step": "hold the line", "who": "host",
             "how": "baresip registered with the did, modules including ctrl_tcp and menu",
             "why": "the invite has to arrive somewhere that is awake"},
            {"step": "see it", "who": "host",
             "how": "read CALL_INCOMING off ctrl_tcp and keep the call id",
             "why": "this is the event that arrives while the call can still be answered"},
            {"step": "answer", "who": "host",
             "how": "send the answer command over the same socket",
             "why": ("the caller gets a voice instead of thirty seconds of ringing, and the agent stops "
                     "racing a clock it cannot see")},
            {"step": "say what it is", "who": "host",
             "how": "the first line names the agent and offers to take a message",
             "why": "the refusal that makes answer-then-tell honest rather than a trick"},
            {"step": "tell the agent", "who": "notifier",
             "how": f"write the event through {channel}",
             "why": "so a decision can arrive even though it was not needed to start the call"},
            {"step": "the agent decides", "who": "agent",
             "how": "talk through the host's audio, which this branch proved on pulseaudio, or hang up",
             "why": "the media is on the host, so a decision can arrive whenever it arrives"},
            {"step": "close it", "who": "host",
             "how": "the hangup command, with the reason in the notification",
             "why": "an answered call that nobody ends is a bill and a silent room"},
        ],
        "budget": RING_BUDGET,
        "channel_row": NOTIFY[channel],
        "refusals": sorted(REFUSED),
    }


def notify_message(event, at=None):
    """what the agent actually reads: the call id, who is calling, and that the clock is running."""
    return {
        "kind": "ringing",
        "call_id": event.get("id") or event.get("call_id"),
        "peer": event.get("peeruri") or event.get("peer"),
        "type": event.get("type", "CALL_INCOMING"),
        "at": at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "state": "answered, waiting for the agent",
        "decide": "talk through the host, or hang up",
        "budget_s": RING_BUDGET["decide_by_s"],
    }


def netstring(payload):
    body = payload if isinstance(payload, bytes) else payload.encode()
    return str(len(body)).encode() + b":" + body + b","


def command(name, params=""):
    """the ctrl_tcp wire shape: params is a string, and the token is ours."""
    return netstring(json.dumps({"command": name, "params": params, "token": "ring"}).encode())


def decode(buffer):
    """messages out of what arrived, plus the remainder. netstrings, and bare json when a peer sends it."""
    messages, rest = [], buffer if isinstance(buffer, bytes) else buffer.encode()
    while rest:
        head = rest[:1]
        if head.isdigit():
            colon = rest.find(b":")
            if colon == -1:
                break
            try:
                length = int(rest[:colon])
            except ValueError:
                break
            start = colon + 1
            if len(rest) < start + length + 1:
                break
            body = rest[start:start + length]
            rest = rest[start + length + 1:]
            try:
                messages.append(json.loads(body))
            except ValueError:
                continue
        elif head in (b"{", b"["):
            depth, end = 0, None
            for index, byte in enumerate(rest):
                if byte in b"{[":
                    depth += 1
                elif byte in b"}]":
                    depth -= 1
                    if depth == 0:
                        end = index + 1
                        break
            if end is None:
                break
            chunk, rest = rest[:end], rest[end:]
            try:
                messages.append(json.loads(chunk))
            except ValueError:
                continue
        else:
            rest = rest[1:]
    return messages, rest


def is_ringing(message):
    return message.get("type") == "CALL_INCOMING" and message.get("class", "call") == "call"


class Ring:
    """listen on ctrl_tcp, answer when a call arrives, and hand the event to a notifier.

    the socket is injected so the whole chain can be proven against a fake baresip, which is the only
    way to pin answer-then-tell without a registration.
    """

    def __init__(self, sock, notify=None, policy="answer-then-tell", auto_answer=True):
        self.sock = sock
        self.notify = notify or (lambda message: None)
        self.policy = policy
        self.auto_answer = auto_answer
        self.seen = []
        self.sent = []
        self._buffer = b""

    def _write(self, payload):
        self.sent.append(payload)
        self.sock.sendall(payload)

    def feed(self, chunk):
        """one read's worth of bytes in, the messages it completed out."""
        messages, self._buffer = decode(self._buffer + chunk)
        for message in messages:
            self.seen.append(message)
            if is_ringing(message):
                if self.auto_answer and self.policy == "answer-then-tell":
                    self._write(command("answer"))
                self.notify(notify_message(message))
        return messages

    def pump(self, until=None, timeout=5.0):
        """read until `until(message)` is true or the socket goes quiet."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = max(0.05, deadline - time.time())
            self.sock.settimeout(remaining)
            try:
                chunk = self.sock.recv(4096)
            except (socket.timeout, TimeoutError):
                return False
            except OSError:
                return False
            if not chunk:
                return False
            messages = self.feed(chunk)
            if until and any(until(m) for m in messages):
                return True
        return False

    def hangup(self):
        self._write(command("hangup"))


def write_notification(message, path=None):
    """the file channel: a jsonl line, because a test and a tail -f both want that."""
    target = path or os.path.join(os.path.expanduser("~"), ".local", "share", "heyphony", "rings.jsonl")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "a") as handle:
        handle.write(json.dumps(message, sort_keys=True) + "\n")
    return target


def first_proof():
    return {
        "call_it": "dial the did from anything, once the host holds the registration",
        "passes_when": ("the host answers inside two seconds, the notification line appears in the queue "
                        "with the peer uri and the call id, and the agent's first sentence is audible to "
                        "the caller through the host's audio"),
        "fails_loudly_when": ("the notification appears and the call never answered, which means the "
                              "policy was tell-then-answer on a slow channel"),
        "without_a_handset": "the caller can be the provider's own test call, or another line we hold",
    }
