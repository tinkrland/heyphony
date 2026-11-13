"""live: one number, two rails, in the same second.

the question this exists to answer is the one a person asks out loud while it is happening:

    "sorry, i just sent you a screenshot instead of explaining"  ... said on a call

that is not exotic. sms and voice are different channels at the carrier, so a text reaches the
number while a call is up, and nothing about the numbering plan stops it. what has to be true is
on our side, and it is three things:

    1. **one process holds both doors.** the invite arrives on the sip socket baresip owns, the text
       arrives as an http post to the catcher. two servers, one program, so neither waits on the
       other. that is why the catcher is now threaded and the call socket is read in its own loop.
    2. **one log, ordered.** a listener that has to poll two places independently cannot say which
       came first, which is the only fact that matters when the caller says "just sent it". every
       event lands in one `Timeline` with a sequence number.
    3. **a wait that watches both.** `next_event` blocks on the timeline's condition, so the loop
       is woken by whichever rail spoke, not by a timer. the alternative, one thread per rail
       appending to separate files, is what makes an agent answer a text that arrived before it
       heard the sentence.

what is proven here and what is not, in the same breath: the two rails running at once is proven
over a fake sip socket and a real http server, because that is the part that is ours. a call over a
real carrier, with a real carrier's mms arriving on it, is not proven and is not claimed. the first
honest run of that is one number, one person, one call, one picture.
"""
import json
import socket
import threading
import time
from http.server import ThreadingHTTPServer

from src.manage import allow, catcher

# the baresip event names this rail cares about, and what a person would call them
CALL_EVENTS = {
    "CALL_INCOMING": "ringing at this number",
    "CALL_RINGING": "ringing at the far end",
    "CALL_ESTABLISHED": "answered, both ways are open",
    "CALL_CLOSED": "hung up",
    "CALL_LOCAL_SDP": None,
    "CALL_REMOTE_SDP": None,
}

RAILS = ("call", "sms")


def netstring(payload):
    """baresip's ctrl_tcp reads netstrings, so a command goes out the way its own module parses it."""
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return str(len(body)).encode() + b":" + body + b","


def decode(buffer):
    """every complete message in a buffer, plus what is left over.

    tolerant on purpose: netstrings are the documented framing, a bare json object is what the
    module's own doc example writes, and a read can split either in half.
    """
    out, data = [], buffer
    while data:
        if data[:1].isdigit():
            head, _, rest = data.partition(b":")
            if not rest:
                break
            try:
                length = int(head)
            except ValueError:
                break
            if len(rest) < length + 1:
                break
            body, data = rest[:length], rest[length + 1:]
            try:
                out.append(json.loads(body))
            except ValueError:
                out.append({"unparsed": body.decode("utf-8", "replace")})
            continue
        start = data.find(b"{")
        if start < 0:
            data = b""
            break
        data = data[start:]
        try:
            message, end = json.JSONDecoder().raw_decode(data.decode("utf-8", "replace"))
        except ValueError:
            break  # a half-read object: kept, and the next read finishes it
        out.append(message)
        data = data[end:]
    return out, data


class Timeline:
    """the one log both rails write to, and the one thing a loop waits on."""

    def __init__(self):
        self._events = []
        self._seq = 0
        self._condition = threading.Condition()

    def add(self, rail, what, **fields):
        with self._condition:
            self._seq += 1
            event = {"seq": self._seq, "at": round(time.time(), 3), "rail": rail, "what": what}
            event.update({k: v for k, v in fields.items() if v is not None})
            self._events.append(event)
            self._condition.notify_all()
            return event

    def events(self, rail=None, since=0):
        with self._condition:
            return [e for e in self._events
                    if e["seq"] > since and (rail is None or e["rail"] == rail)]

    def next_event(self, since=0, rails=RAILS, timeout=None):
        """the first event after `since` on either rail. this is the wait that watches both."""
        deadline = None if timeout is None else time.time() + timeout
        with self._condition:
            while True:
                for event in self._events:
                    if event["seq"] > since and event["rail"] in rails:
                        return event
                left = None if deadline is None else deadline - time.time()
                if left is not None and left <= 0:
                    return None
                self._condition.wait(None if left is None else max(0.01, left))

    def first(self, rail=None, what=None):
        for event in self.events(rail):
            if what is None or event["what"] == what:
                return event
        return None

    def between(self, first_seq, last_seq):
        """what happened while one thing was in progress, which is the whole point of one log."""
        return [e for e in self.events() if first_seq < e["seq"] < last_seq]

    def __len__(self):
        return len(self._events)


class CallRail:
    """the call half: baresip's ctrl_tcp socket, read in a loop, translated into one log."""

    def __init__(self, timeline, sock=None, addr=("127.0.0.1", 4444), timeout=1.0):
        self.timeline = timeline
        self.sock = sock
        self.addr = addr
        self.timeout = timeout
        self._buffer = b""
        self.open = False
        if self.sock is not None:
            # a supplied socket is set up here too: a read with no timeout is a loop nothing can stop
            self.sock.settimeout(self.timeout)

    def connect(self):
        if self.sock is None:
            self.sock = socket.create_connection(self.addr, timeout=self.timeout)
        # a read that can block forever is a loop that cannot be told to stop, so this is set on a
        # supplied socket too, which is what the tests hand over
        self.sock.settimeout(self.timeout)
        self.open = True
        self.timeline.add("call", "socket open", where="%s:%s" % self.addr)
        return self

    def command(self, name, params=""):
        """params is a *string* in baresip's protocol, which is the trap the old code hit."""
        if self.sock is None:
            return {"ok": False, "why": "not connected"}
        payload = {"command": name, "params": str(params), "token": "heyphony"}
        try:
            self.sock.sendall(netstring(payload))
            return {"ok": True, "command": name, "params": str(params)}
        except OSError as error:
            return {"ok": False, "why": str(error)}

    def place(self, to):
        """place the call from this process, so the socket that dialled it is the socket watching it.

        the same `dial` verb the calling lane sends, on the same socket, with one difference that is the
        whole point: this one does not hang up its connection afterwards. baresip reports ringing,
        established and closed down the connection a command arrived on, so a dialer that closes on
        accept is a dialer that then has to guess what happened.
        """
        uri = str(to) if ":" in str(to) else "sip:%s" % to
        sent = self.command("dial", uri)
        self.timeline.add("call", "dialled from here", uri=uri, sent=bool(sent.get("ok")),
                          why=None if sent.get("ok") else sent.get("why"))
        return {"ok": bool(sent.get("ok")), "uri": uri, "sent": sent}

    def answer(self):
        return self.command("answer")

    def hangup(self):
        return self.command("hangup")

    def read_once(self):
        """one read, translated. returns the events it carried so a test can assert on them."""
        if self.sock is None:
            return []
        try:
            chunk = self.sock.recv(65536)
        except socket.timeout:
            return []
        except OSError:
            self.open = False
            return []
        if not chunk:
            self.open = False
            return []
        self._buffer += chunk
        messages, self._buffer = decode(self._buffer)
        landed = []
        for message in messages:
            landed += self._translate(message)
        return landed

    def _translate(self, message):
        if not isinstance(message, dict):
            return []
        name = message.get("type")
        if not isinstance(name, str) or name not in CALL_EVENTS:
            return []
        said = CALL_EVENTS[name]
        if said is None:
            return []
        return [self.timeline.add("call", said, kind=name, peer=message.get("peeruri"),
                                  call=message.get("id"))]

    def pump(self, seconds=None, answer_on_incoming=False, stop=None):
        """the loop. bounded by seconds when a caller wants a recording, unbounded when it does not."""
        deadline = None if seconds is None else time.time() + seconds
        answered = False
        while True:
            if stop is not None and stop():
                break
            self.read_once()
            if answer_on_incoming and not answered:
                if self.timeline.first("call", "ringing at this number"):
                    self.answer()
                    self.timeline.add("call", "answered from here")
                    answered = True
            if deadline is not None and time.time() >= deadline:
                break
            time.sleep(0.02)
        return self.timeline.events("call")


class InboxRail:
    """the text half: the catcher on its own thread, writing arrivals into the same log."""

    def __init__(self, timeline, port=8099, path=None, token=None, policy=None):
        self.timeline = timeline
        self.port = port
        self.path = path
        self.token = token
        self.policy = policy
        self.server = None
        self.thread = None

    def start(self):
        # a policy handed in may name one field, and allow.decide reads eight of them, so it is
        # completed from the default rather than raising inside a webhook nobody is watching
        policy = None
        if self.policy:
            policy = dict(allow.default_policy())
            policy.update(self.policy)
        handler = catcher.make_handler(self.token, self.path, policy, on_store=self._stored)
        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.timeline.add("sms", "webhook listening", port=self.port)
        return self

    def _stored(self, entry, stored, reason):
        self.timeline.add("sms", "text arrived" if stored else "text refused",
                          sender=entry.get("sender"), body=entry.get("body"),
                          media=entry.get("media") or [], message=entry.get("id"),
                          reason=None if stored else reason)

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            self.timeline.add("sms", "webhook closed", port=self.port)


class Session:
    """both rails, one lifetime. start it, then wait on the log rather than on a rail."""

    def __init__(self, timeline=None, call=None, inbox=None):
        self.timeline = timeline or Timeline()
        self.call = call or CallRail(self.timeline)
        self.inbox = inbox or InboxRail(self.timeline)

    def start(self, connect=True):
        self.inbox.start()
        if connect:
            try:
                self.call.connect()
            except OSError as error:
                self.timeline.add("call", "no sip socket", why=str(error))
        return self

    def hangup(self):
        """end a call this session placed. named separately from stop, because stop closes a socket."""
        if not self.call.open:
            return {"ok": False, "why": "the call socket is not open"}
        sent = self.call.hangup()
        self.timeline.add("call", "hung up from here", sent=bool(sent.get("ok")))
        return sent

    def stop(self):
        self.inbox.stop()
        if self.call.sock is not None:
            try:
                self.call.sock.close()
            except OSError:
                pass
            self.call.open = False
            self.timeline.add("call", "socket closed")

    def place(self, to):
        """place a call through the call rail, before the wait begins."""
        placed = self.call.place(to)
        self.timeline.add("call", "placing call", uri=placed["uri"])
        return placed

    def waiting(self, seconds=30, answer=True):
        """hold both open, and hand back whatever the rails said, in order."""
        stop = {"at": time.time() + seconds}
        reader = threading.Thread(target=self.call.pump,
                                  kwargs={"answer_on_incoming": answer,
                                          "stop": lambda: time.time() > stop["at"]},
                                  daemon=True)
        reader.start()
        while time.time() < stop["at"]:
            time.sleep(0.02)
        return self.timeline.events()


def plan():
    """the answer to 'can it be on a call and take a text at the same time', as data."""
    return {
        "shipped": True,
        "what": ("the call rail (baresip ctrl_tcp) and the text rail (the carrier's webhook) in one "
                 "process, writing one ordered log, with a wait that is woken by either"),
        "rails": {"call": ("sip invite on the socket baresip owns, answered from here, or placed from "
                           "here with --dial, in which case the socket that dialled is the socket that "
                           "watches"),
                  "call_out": "dial/answer/hangup on baresip's ctrl_tcp, token-matched replies",
                  "sms": "the catcher, now threaded, so a webhook never queues behind a call"},
        "timeline": ["seq", "at", "rail", "what", "sender", "body", "media", "peer", "call"],
        "media": "an inbound url is kept on the envelope; manage.media.fetch downloads it under a cap",
        "not_included": [
            "a real carrier: no registration and no carrier mms were used, so the shapes are pinned "
            "against baresip's own protocol and the providers' documented payloads, not against a bill",
            "a second number: both rails belong to one did, which is the point",
            "barge-in: the agent answers a text by speaking, and interrupting itself mid-sentence is "
            "not implemented",
        ],
        "refused": ["one-rail-at-a-time", "poll-two-files-and-guess-the-order",
                    "answer-the-text-after-the-call-ends"],
    }
