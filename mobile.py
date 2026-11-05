"""mobile: the phone as a device, and the line's relationship to it.

a number proves a line. it does not prove a device. the flows that ask for hardware want the
second thing, and no sid or did will ever satisfy them, so this branch exists to say which
device we hold, what an agent can do to it, and where the sip secret is allowed to live.

two halves, and the second one is this branch's own:

  the verbs    a phone has no dom. the closest thing is the accessibility tree, and android
               dumps it over adb, which is why four verbs are enough there. ios keeps that
               tree inside the phone, so mirroring exposes pixels and ocr reads them. the
               four names are borrowed from phone-harness's local mode (mit, the project that
               drives your own phone); the contract is worth taking, a device we do not own
               is not. our own mobile guests and a phone on a desk are what we drive.

  the line     heyphony registers a did on a host it controls. a phone is a second machine, and
               a did is ONE registration, so "put the number on the phone" is not a second
               line, it is a race between two machines. every route below says where the
               secret ends up, because that is the decision, not the app choice.
"""

VERBS = ("open_app", "tap_text", "type_text", "screen")

BACKENDS = {
    "android-adb": {
        "verbs": list(VERBS),
        "covers": "our own android guest, and a real android phone over usb or wi-fi",
        "why": ("the accessibility tree is dumpable over adb (uiautomator), so a label becomes a "
                "coordinate without a driver and a tap is never a guess"),
        "holds": "our own device and our own account",
        "state": "designed",
    },
    "ios-mirroring": {
        "verbs": ["screen"],
        "covers": "our own iphone, mirrored on a mac",
        "why": ("mirroring gives pixels and vision ocr reads them; the accessibility tree never leaves "
                "the phone, so there is no label to tap by"),
        "holds": "our own phone, eyes only",
        "state": "designed",
    },
    "ios-guest": {
        "verbs": [],
        "covers": "a simulator guest",
        "why": ("a simulator has no springboard to tap and no tree to read, and it cannot answer a "
                "hardware check, so no verb is honest here"),
        "holds": "nothing",
        "state": "refused",
    },
}

# where the did's password ends up, which is the whole decision on this branch
LINE_ROUTES = {
    "host-holds-the-line": {
        "what": ("the did stays registered on the host that heyphony already runs, and the phone is "
                 "only ever the device: the app that wants hardware, the screen, the sensors"),
        "secret_on": "the host, where it already lives",
        "phone_keeps_it": False,
        "secrets_to_rotate": 0,
        "survives_phone_burn": True,
        "registrations": 1,
        "needs": [],
        "honest": ("the phone cannot answer the did, and does not need to. the number rings the host "
                   "and the phone is the identity that some flows actually inspect"),
        "state": "designed",
    },
    "app-registers-the-did": {
        "what": ("a sip client on the phone (linphone, or baresip on android) registers the did itself, "
                 "so the phone rings and talks without the host in the path"),
        "secret_on": "the phone, in the client's own config",
        "phone_keeps_it": True,
        "secrets_to_rotate": 1,
        "survives_phone_burn": False,
        "registrations": 1,
        "needs": ["the host stops registering first, or two machines fight over one registration"],
        "honest": ("a burnable guest holding a long-lived sip password is the exact shape this repo "
                   "refuses everywhere else: the secret outlives the guest and has to be re-issued "
                   "every spawn"),
        "state": "designed",
    },
    "provision-onto-phone": {
        "what": ("the config is pushed to the phone over adb instead of typed into it: one push, one "
                 "app restart, and no human typing a password on a screen"),
        "secret_on": "the phone, pushed from the host",
        "phone_keeps_it": True,
        "secrets_to_rotate": 1,
        "survives_phone_burn": False,
        "registrations": 1,
        "needs": ["adb write access to the app's config path", "the app reads it on next launch"],
        "honest": ("this is the same secret placement as the row above, with less typing. it removes "
                   "the human, not the exposure, and the file it writes is a password at rest"),
        "state": "designed",
    },
    "termux-ssh": {
        "what": ("a shell on the phone over ssh (termux's sshd), so the host can run commands there. a "
                 "desktop ssh client on the phone is the same door seen from the other side"),
        "secret_on": "the phone, in whatever the shell writes",
        "phone_keeps_it": True,
        "secrets_to_rotate": 1,
        "survives_phone_burn": False,
        "registrations": 1,
        "needs": ["termux installed", "sshd started by hand", "a key that survives the burn"],
        "honest": ("a shell is not what is missing here: the missing verb is pressing things in apps, "
                   "and adb already does that. ssh earns its place for moving a file, and adb push "
                   "already does that too"),
        "state": "designed",
    },
    "phone-holds-the-account": {
        "what": ("the phone owns the account and the session (the app is logged in on it), and the "
                 "number stays where it is. two different things, on purpose"),
        "secret_on": "the phone holds a session, not the sip password",
        "phone_keeps_it": False,
        "secrets_to_rotate": 0,
        "survives_phone_burn": False,
        "registrations": 1,
        "needs": ["the account exists first", "the phone is the device of record, so it cannot be a "
                  "scratch guest that dies after the check"],
        "honest": ("owning an account is not a job, but it is state: whatever creates it has to live on "
                   "the identity that will use it, or the login strands the way a session does"),
        "state": "designed",
    },
}

# what a flow can actually see, and what each kind of device we hold can answer
CHECKS = {
    "sms-code": {
        "sees": "a number that receives a text",
        "a_did_answers": "yes, unless the sender refuses voip ranges",
        "a_phone_we_hold_answers": "yes",
        "a_guest_answers": "yes, the text lands in the guest",
        "why": "this is main's half already. a number on a host receives a code",
    },
    "device-attestation": {
        "sees": "a signed verdict from the platform (play integrity, device check) about genuine hardware",
        "a_did_answers": "no, and no number type changes that",
        "a_phone_we_hold_answers": "yes, when the platform services are present and the keys were never borrowed",
        "a_guest_answers": "no: the verdict is computed from hardware keys a guest does not have",
        "why": "this is the check that makes a phone worth having at all",
    },
    "sim-presence": {
        "sees": "a sim, and the carrier behind it",
        "a_did_answers": "no",
        "a_phone_we_hold_answers": "yes, physical or an esim on a device we keep",
        "a_guest_answers": "only as a story: the mcc and the exit geography have to agree, and a guest rarely does",
        "why": "a sim is a mobile identity, which is the thing a sip did is not",
    },
    "sensor-tells": {
        "sees": "accelerometer and gyro sampling rates, noise floors, software renderers, build keys",
        "a_did_answers": "no",
        "a_phone_we_hold_answers": "yes, because hardware cannot help telling",
        "a_guest_answers": "no: fixed rates with no noise, a software renderer name and test-keys all say guest",
        "why": "the tells module in spawnables exists for exactly this, and it fails a guest rather than teaching it to lie",
    },
    "camera": {
        "sees": "a live camera, and sometimes a face",
        "a_did_answers": "no",
        "a_phone_we_hold_answers": "yes by hand, no by automation",
        "a_guest_answers": "no",
        "why": ("the four verbs do not include a camera, no adb input injects one, and a flow that "
                "wants a face wants a person"),
    },
    "unlabelled-control": {
        "sees": "an icon with no text",
        "a_did_answers": "no",
        "a_phone_we_hold_answers": "on android yes, because the tree carries a content description",
        "a_guest_answers": "on android yes; on ios no, mirroring is pixels and ocr reads text, not icons",
        "why": "this is the boundary of the four verbs, and it is honest on both platforms",
    },
}

REFUSED = {
    "borrowed-identity": "a device somebody else owns may be driven and may not become the identity",
    "ocr-pretending-to-press": "vision reads; a tap needs a coordinate somebody can vouch for",
    "silent-tap": "a tap without a dump is a guess with a screenshot attached",
    "secret-in-burn": ("a guest that dies takes a long-lived sip password with it and needs a new one "
                       "every spawn, so that placement is refused as a default rather than offered"),
    "attestation-fiction": ("a guest that reports genuine hardware is the one lie this branch will not "
                            "build: the verdict is signed, and faking it is the attack, not the workaround"),
    "camera-pretending": "a camera flow gets a person, not four verbs and a screenshot",
}


def why_no_dom():
    """the sentence worth quoting when somebody asks why a phone needs four verbs."""
    return ("a phone has no dom. android dumps the accessibility tree over adb, so a label becomes a "
            "coordinate and four verbs cover it. ios keeps that tree inside the phone, so mirroring "
            "gives pixels and ocr reads them. one platform has an api, the other has a camera.")


def recommend():
    """the route this branch would pick, and the reason, in one call."""
    route = LINE_ROUTES["host-holds-the-line"]
    return {"route": "host-holds-the-line", "why": route["honest"],
            "because": ("the phone is needed for the device checks, never for the ringing, and a "
                        "secret that never reaches the phone cannot leak from it"),
            "state": route["state"]}


def route(name):
    if name not in LINE_ROUTES:
        raise ValueError(f"unknown route {name!r}; the set is {sorted(LINE_ROUTES)}")
    return LINE_ROUTES[name]


def routes_that_keep_the_secret_off_the_phone():
    return [k for k, v in LINE_ROUTES.items() if not v["phone_keeps_it"]]


def check(name):
    if name not in CHECKS:
        raise ValueError(f"unknown check {name!r}; the set is {sorted(CHECKS)}")
    return CHECKS[name]


def checks_a_guest_fails():
    """the checks where our own guest is not the answer, which is why a phone is held at all."""
    return [k for k, v in CHECKS.items() if v["a_guest_answers"].startswith("no")]


def plan(verb, backend="android-adb", **kw):
    """verb plus backend, into the argv adb takes, or a refusal with the reason."""
    if verb not in VERBS:
        raise ValueError(f"unknown verb {verb!r}; the set is {VERBS}")
    table = {"open_app": _open_app, "tap_text": _tap_text, "type_text": _type_text, "screen": _screen}
    return table[verb](backend, **kw)


def _refused(verb, backend):
    spec = BACKENDS.get(backend)
    if not spec:
        return {"refused": True, "verb": verb, "why": f"unknown backend {backend!r}"}
    if not spec["verbs"]:
        return {"refused": True, "verb": verb, "backend": backend, "why": spec["why"],
                "alternatives": ["android-adb"]}
    return {"refused": True, "verb": verb, "backend": backend,
            "why": f"{backend} offers {spec['verbs']}, not {verb}",
            "reason": (REFUSED["ocr-pretending-to-press"] if backend == "ios-mirroring"
                       else spec["why"])}


def _open_app(backend, pkg=None, **_):
    if backend != "android-adb":
        return _refused("open_app", backend)
    if not pkg:
        return {"needs": ["pkg"], "why": "an app is started by package name, not by label"}
    return ["adb", "shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"]


def dump_tree():
    return ["adb", "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"]


def read_tree():
    return ["adb", "shell", "cat", "/sdcard/window_dump.xml"]


BOUNDS = __import__("re").compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def find_node(xml_text, label):
    """the first node whose text or description is the label, as a centre point.

    pure on purpose: the interesting half of a tap is the parse, and the parse is testable with
    no phone anywhere near it.
    """
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"not an accessibility dump: {exc}")
    seen = []
    for node in root.iter():
        text = node.get("text") or ""
        desc = node.get("content-desc") or ""
        if text:
            seen.append(text)
        if label and label.lower() in (text.lower(), desc.lower()):
            match = BOUNDS.search(node.get("bounds") or "")
            if not match:
                continue
            x1, y1, x2, y2 = (int(g) for g in match.groups())
            return {"x": (x1 + x2) // 2, "y": (y1 + y2) // 2,
                    "label": text or desc, "bounds": (x1, y1, x2, y2)}
    raise LookupError(f"no node says {label!r}; the tree offers {seen[:12]}")


def _tap_text(backend, label=None, xml_text=None, **_):
    if backend != "android-adb":
        return _refused("tap_text", backend)
    if xml_text is None:
        return {"needs": ["dump_tree", "read_tree"], "then": "plan('tap_text', label=..., xml_text=...)",
                "why": REFUSED["silent-tap"]}
    node = find_node(xml_text, label)
    return ["adb", "shell", "input", "tap", str(node["x"]), str(node["y"])]


def escape_text(text):
    """adb's shell eats spaces unless they are %s, and it is not a shell we can quote around."""
    return (text or "").replace("%", "\\%").replace(" ", "%s")


def _type_text(backend, text=None, **_):
    if backend != "android-adb":
        return _refused("type_text", backend)
    return ["adb", "shell", "input", "text", escape_text(text)]


def _screen(backend, **_):
    if backend == "android-adb":
        return ["adb", "exec-out", "screencap", "-p"]
    if backend == "ios-mirroring":
        return {"argv": ["screencapture", "-x", "frame.png"],
                "note": "the mirroring window, then vision ocr; pixels are all we get and all we claim"}
    return _refused("screen", backend)


def status():
    return {
        "branch": "mobile",
        "verbs": list(VERBS),
        "backends": {k: {"verbs": v["verbs"], "state": v["state"]} for k, v in BACKENDS.items()},
        "line": {"recommended": recommend()["route"],
                 "secret_stays_off_the_phone": routes_that_keep_the_secret_off_the_phone()},
        "guest_fails": checks_a_guest_fails(),
        "verified": [k for k, v in LINE_ROUTES.items() if v["state"] == "verified"],
        "adopted_from": ("phone-harness's local mode (mit): open_app, tap_text, type_text, screen, on a "
                         "phone we hold"),
    }
