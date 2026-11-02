"""the socket: baresip's ctrl_tcp, spoken the way the module's own source says to speak it.

verified from the source rather than from a blog post, because a wrong guess here does not fail, it
hangs. three facts that decide the whole file:

- a command is `{"command": ..., "params": ..., "token": ...}`, and `params` is a **string**, not an
  object. the module's own example is `{"command": "dial", "params": "sip:alice@atlanta.com"}`.
- a response is `{"response": true, "ok": bool, "data": "...", "token": "..."}`.
- an event is `{"event": ..., "class": "call", "type": "CALL_CLOSED", "param": "...", "peeruri": ...}`,
  and the module writes `"event": true` as a *string* in its own documented example while `response`
  is a boolean. the reader accepts both, because the example is the contract and it is inconsistent.

framing: bytes coming in are netstring framed (`netstring_insert` in the module's read handler) and
the module reserves `NETSTRING_HEADER_SIZE` bytes before every json it sends. so this writes
netstrings and reads netstrings, while also accepting a bare json object, since a reserved header that
nothing fills is a shape that parses and a lane that strands is worse than a lane that is tolerant.
"""
import json
import socket
import time
import uuid

TOKEN = "callheavy"


def netstring(payload):
    """`<len>:<payload>,`. the one line of framing baresip's read path expects."""
    body = payload if isinstance(payload, bytes) else payload.encode()
    return str(len(body)).encode() + b":" + body + b","


def encode(message):
    return netstring(json.dumps(message, separators=(",", ":")).encode())


def decode(buffer):
    """messages out of whatever arrived, and the unconsumed remainder. tolerant by design."""
    messages, rest, junk = [], buffer, b""

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
            if rest[start + length:start + length + 1] != b",":
                raise ValueError("netstring is not terminated with a comma")
            messages.append(rest[start:start + length])
            rest = rest[start + length + 1:]
        elif head in (b"{", b"["):
            text = rest.decode("utf-8", "replace")
            try:
                _, end = json.JSONDecoder().raw_decode(text)
            except ValueError:
                break
            consumed = len(text[:end].encode())
            messages.append(rest[:consumed])
            rest = rest[consumed:]
        else:
            trimmed = rest.lstrip(b"\r\n\t ")
            if trimmed == rest:
                junk += rest[:1]
                rest = rest[1:]
            else:
                rest = trimmed

    out = []
    for chunk in messages:
        try:
            out.append(json.loads(chunk))
        except ValueError:
            continue
    if junk:
        rest = junk + rest
    return out, rest


def classify(message):
    """response, event or noise. the module's own quirk: `"event": "true"` is a string."""
    if not isinstance(message, dict):
        return "noise", message
    if "response" in message:
        return "response", message
    if "event" in message:
        flag = message.get("event")
        if flag is True or str(flag).lower() == "true":
            return "event", message
    return "noise", message


class Socket:
    """the transport, kept small so a test can stand in for it and prove the driver without baresip."""

    def __init__(self, host="127.0.0.1", port=4444, timeout=10.0):
        self.address = (host, port)
        self.sock = socket.create_connection(self.address, timeout=timeout)
        self.buffer = b""
        self.closed = False

    def send(self, message):
        self.sock.sendall(encode(message))
        return message

    def recv(self, timeout=None):
        """a list of messages, or None when the wait expired. `closed` says the peer hung up."""
        if timeout is not None:
            self.sock.settimeout(max(0.01, timeout))
        try:
            chunk = self.sock.recv(65536)
        except socket.timeout:
            return None
        if not chunk:
            self.closed = True
            return []
        self.buffer += chunk
        messages, self.buffer = decode(self.buffer)
        return messages

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def command(name, params=""):
    """every command is this. params is a string; a dict here is the mistake that earns a warning log."""
    return {"command": name, "params": params if isinstance(params, str) else json.dumps(params),
            "token": TOKEN}


def result_shape(**fields):
    """every return from `dial` has these keys, including the failures. a shape that changes with the
    outcome is how a caller ends up with a KeyError instead of a diagnosis."""
    base = {"ok": False, "accepted": None, "stopped": None, "uri": None, "ringing": None,
            "established": None, "closed": None, "call_outcome": None, "duration_s": None,
            "events": []}
    base.update(fields)
    return base


def dial(uri, transport=None, host="127.0.0.1", port=4444, settle=45.0, connect_timeout=10.0,
         clock=time.monotonic, sleep=time.sleep):
    """place one call and follow it until it ends, without ever claiming more than the socket said.

    `settle` is how long to keep listening after the dial is accepted. a call that is still ringing at
    the deadline is reported as ringing, not as failed, because a person deciding not to answer is a
    fact about the world rather than an error in the client.
    """
    own = transport is None
    transport = transport or Socket(host, port, timeout=connect_timeout)
    token = uuid.uuid4().hex[:8]
    started = clock()
    log = []

    try:
        transport.send({"command": "dial", "params": uri, "token": token})
    except OSError as error:
        if own:
            transport.close()
        return result_shape(stopped="no-socket", uri=uri, error=str(error),
                            why="ctrl_tcp is not reachable. is baresip running, and is ctrl_tcp.so loaded")

    accepted = None
    ringing = established = closed = None
    deadline = started + settle

    while clock() < deadline:
        remaining = max(0.05, min(1.0, deadline - clock()))
        messages = transport.recv(timeout=remaining)
        if messages is None:
            continue
        for message in messages:
            kind, body = classify(message)
            log.append({"kind": kind, "at": round(clock() - started, 2), "message": body})
            if kind == "response" and body.get("token") == token:
                accepted = bool(body.get("ok"))
                if not accepted:
                    if own:
                        transport.close()
                    return result_shape(stopped="refused", uri=uri, accepted=False,
                                        error=body.get("data"), events=log,
                                        why="baresip refused the dial verb itself")
            elif kind == "event":
                name = str(body.get("type") or "")
                if name == "CALL_RINGING":
                    ringing = clock() - started
                elif name == "CALL_ESTABLISHED":
                    established = clock() - started
                elif name == "CALL_CLOSED":
                    closed = {"reason": body.get("param"), "at": round(clock() - started, 2)}
        if closed:
            break
        if getattr(transport, "closed", False):
            break

    if own:
        transport.close()

    outcome = "completed" if established is not None else ("no_answer" if ringing is not None else "busy")
    if closed and closed.get("reason") and "declin" in str(closed.get("reason")).lower():
        outcome = "declined"

    return result_shape(
        ok=bool(accepted), accepted=accepted,
        stopped="closed" if closed else ("transport-closed" if getattr(transport, "closed", False)
                                         else "deadline"),
        uri=uri, ringing=ringing, established=established, closed=closed, call_outcome=outcome,
        duration_s=round(closed["at"] - established, 2) if (closed and established is not None) else None,
        events=log,
        note="this is what the client saw. the carrier's own record is the authority on billing")


def hangup(transport=None, host="127.0.0.1", port=4444):
    own = transport is None
    transport = transport or Socket(host, port)
    try:
        transport.send(command("hangup"))
        return {"ok": True, "sent": "hangup"}
    except OSError as error:
        return {"ok": False, "error": str(error)}
    finally:
        if own:
            transport.close()


def answer(transport=None, host="127.0.0.1", port=4444):
    own = transport is None
    transport = transport or Socket(host, port)
    try:
        transport.send(command("answer"))
        return {"ok": True, "sent": "answer"}
    except OSError as error:
        return {"ok": False, "error": str(error)}
    finally:
        if own:
            transport.close()
