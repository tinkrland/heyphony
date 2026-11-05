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
        "wake": None,
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
                 "so the phone can ring and talk without the host in the path, while the app is awake"),
        "wake": ("android-app", "ios-app"),
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
        "wake": ("android-app", "ios-app"),
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
        "wake": None,
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
        "wake": None,
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


# the acts that belong to a person: the phone is a device somebody holds, not a service we rent
FROM_OWNER = [
    {"act": "connect the phone and accept the debugging prompt",
     "why": ("adb, over a cable or the same wifi, needs an authorization the owner taps on the phone, and "
             "an unauthorized device refuses every verb below")},
    {"act": "unlock the phone, and leave it awake while a job runs",
     "why": ("a locked android blocks the accessibility dump and a locked iphone stops mirroring. the "
             "verbs are not wrong in that state, the screen is asleep")},
    {"act": "sign into the app the phone has to carry",
     "why": ("installing is ours and an account is the owner's, including whatever verification the "
             "service wants for it")},
    {"act": "be present for a check that wants a face or a camera",
     "why": ("the four verbs are taps and typing. a flow that opens the camera gets a person, and this "
             "branch says so instead of pretending the screenshot is a liveness test")},
]

AREAS = {
    "what can this phone do": {
        "asks": "which verbs a backend offers, and why one of them has fewer",
        "command": "bin/mobile verbs --backend android-adb",
        "answers": "the verb list for the backend plus the reason it is shorter on ios"},
    "where does the number live": {
        "asks": "whether the did's password goes on the phone at all",
        "command": "bin/mobile routes",
        "answers": "every route with where the secret ends up, and the one this branch recommends"},
    "what can a flow actually see": {
        "asks": "which device checks a guest phone cannot pass",
        "command": "bin/mobile checks",
        "answers": "the check table and the list a guest fails, which is why a phone we hold is the point"},
    "does the phone ring when it is idle": {"asks": "will the screen light up, and where does the answer differ",
                                            "command": "bin/mobile wake",
                                            "answers": ("three rows: the android app, the iphone app, and the "
                                                        "carrier forwarding to the phone's own number, with what "
                                                        "wakes each one and what we can force")},
    "can the agent answer a call on the phone": {"asks": "who ends up in the call, and can it hear",
                                                 "command": "bin/mobile answer",
                                                 "answers": ("three shapes: the host softphone answers, the phone "
                                                             "taps answer and the audio stays in the handset, or an "
                                                             "app we ship joins a room")},
    "how do i prove it works": {
        "asks": "the cheapest first success on a phone somebody is holding",
        "command": "bin/mobile prove",
        "answers": "the ladder in order, each step with the argv and the thing to watch out for"},
}


def _argv(out):
    """plan() answers a list when the verb is possible and an object when it has something to say."""
    return out["argv"] if isinstance(out, dict) and "argv" in out else out


def prove_plan():
    """the first success, cheapest first, with argv taken from plan() rather than retyped here."""
    iphone_screen = _argv(plan("screen", backend="ios-mirroring"))
    return [
        {"step": "one authorized device",
         "backend": "android-adb",
         "proves": "the host can see the phone at all",
         "argv": ["adb", "devices"],
         "watch_out": ("the word after the serial has to be device, not unauthorized: unauthorized means "
                       "nobody has tapped allow on the phone yet"),
         "state": "designed"},
        {"step": "open a stock app",
         "backend": "android-adb",
         "proves": "a package launches by name, which is the whole of open_app",
         "argv": _argv(plan("open_app", pkg="com.android.dialer")),
         "watch_out": "a renamed or uninstalled package fails here, so name one the phone actually has",
         "state": "designed"},
        {"step": "take one frame",
         "backend": "android-adb",
         "proves": "a png comes back, which is what an agent looks at when text is not enough",
         "argv": _argv(plan("screen")),
         "watch_out": "a locked phone screenshots the lock screen, and that is a pass with nothing to read",
         "state": "designed"},
        {"step": "dump the accessibility tree",
         "backend": "android-adb",
         "proves": "labels are readable as text before anything is pressed",
         "argv": [dump_tree(), read_tree()],
         "watch_out": ("uiautomator writes to /sdcard and can fail on a phone with no writable storage, "
                       "which looks like an empty dump rather than an error"),
         "state": "designed"},
        {"step": "tap a label out of that dump",
         "backend": "android-adb",
         "proves": "a label becomes a coordinate, which is the only honest way to press",
         "needs": ["dump_tree", "read_tree"],
         "then": "plan('tap_text', label=..., xml_text=<the dump>)",
         "watch_out": "a tap without a dump is refused here on purpose, and find_node is pure so this is testable first",
         "state": "designed"},
        {"step": "type into what has focus",
         "backend": "android-adb",
         "proves": "text reaches a field, with spaces and percent signed the way input text wants them",
         "argv": _argv(plan("type_text", text="hello world")),
         "watch_out": "nothing focused means the text goes nowhere silently",
         "state": "designed"},
        {"step": "the same look on an iphone",
         "backend": "ios-mirroring",
         "proves": "mirroring gives a frame, and only a frame",
         "argv": iphone_screen,
         "watch_out": "tap_text stays refused on ios, so this step proves the camera and not a hand",
         "state": "designed"},
    ]


def setup_plan():
    """the branch in one object, in the shape the rest of the repo answers --setup with."""
    return {
        "branch": "mobile",
        "what_this_is": ("the phone as a device, and the decision about where the number's password may "
                         "live. a did proves a line; these flows ask what the hardware is"),
        "linchpin": recommend(),
        "from_owner": FROM_OWNER,
        "env": {"required": [],
                "optional": [],
                "note": ("no secret enters this branch. adb trusts the cable or the paired host, and the "
                         "did's password stays where the routes put it, which is the host")},
        "areas": AREAS,
        "prove": prove_plan(),
        "rules": dict(REFUSED),
        "backends": {k: {"verbs": v["verbs"], "state": v["state"]} for k, v in BACKENDS.items()},
        "verified": [k for k, v in LINE_ROUTES.items() if v["state"] == "verified"],
        "state": "designed",
    }


# whether a phone actually wakes for a call, which is a different question from whether it registered
WAKE = {
    "android-app": {
        "what": "a sip app on android, registered, holding a foreground service",
        "wake_on_ring": ("yes, on a phone we own: whitelist the app from doze (adb shell cmd deviceidle "
                         "whitelist +<pkg>), let it hold a foreground service, and the full screen intent turns "
                         "the panel on when the invite lands, locked screen and all"),
        "answer": "phone-taps-answer",
        "invite_while_idle": ("not reliably: doze parks the app's network and stops its keepalive, so the carrier "
                              "believes the registration is live while the invite never reaches the phone"),
        "lights_the_screen": ("yes, once the invite lands: an incoming call is one of the few cases android still "
                              "allows a full screen intent, so the app can light the panel over the lock screen"),
        "lever_we_hold": ("on a phone we control, adb: svc power stayon keeps the panel alive while charging and "
                          "dumpsys deviceidle shows what doze actually did, but both trade the thing that makes it "
                          "a phone for a handset that behaves like a desk terminal"),
        "honest": ("registered is not ringing. the gap between them is doze, and nothing in the four verbs closes "
                   "it"),
        "state": "designed",
    },
    "ios-app": {
        "what": "a sip app on an iphone, backgrounded",
        "wake_on_ring": ("no from this branch: a suspended app cannot wake itself, so the wake has to be a "
                         "pushkit notification with an apns key and the app's own entitlement, and even awake the "
                         "call screen is system ui we only ever see as pixels"),
        "answer": None,
        "invite_while_idle": ("no: ios suspends the app and closes the socket within seconds of the screen locking, "
                              "so the registration the app made is gone by the time a call arrives"),
        "lights_the_screen": ("only through callkit, which means the system draws the call screen. an app ringing "
                              "without pushkit and callkit cannot wake a locked iphone at all"),
        "lever_we_hold": ("none from this branch: the wake path is apns plus the app's own push entitlement, which "
                          "is a signing and server decision rather than an adb one"),
        "honest": ("on ios the ring is a push notification wearing a phone call's clothes, and the sender is not us"),
        "state": "designed",
    },
    "pstn-handset": {
        "what": "the carrier forwards the did to the phone's own mobile number",
        "wake_on_ring": "yes, and it asks nothing of us: the handset radio wakes for a call the sim is being rung on",
        "answer": None,
        "invite_while_idle": ("yes: the handset's own telephony stack answers, not an app, so neither doze nor "
                              "suspension applies"),
        "lights_the_screen": "yes, always, because it is a real call to the sim",
        "lever_we_hold": ("a forwarding rule on the number record at the carrier, which is the other branch's "
                          "errand rather than this one's"),
        "honest": "the phone rings and a person picks up. the agent is no longer the callee, which is the price",
        "state": "designed",
    },
}


def wake(name):
    return WAKE[name]


def wake_rows():
    return [{"name": k, "lights_the_screen": v["lights_the_screen"],
             "invite_while_idle": v["invite_while_idle"], "state": v["state"]} for k, v in WAKE.items()]


def routes_that_can_ring():
    """the routes whose phone is meant to answer, so the wake question applies to them at all."""
    return [k for k, v in LINE_ROUTES.items() if v.get("wake")]


# who actually answers the call, which is the half the waking does not settle
ANSWER_PATH = {
    "host-softphone": {
        "what": ("a console sip client on the host answers: baresip or pjsua as a process, the did rings there "
                 "and the media is a local audio device or a file"),
        "agent_hears": "yes, because the media lands on a machine we run and can point at a pipe or a wav",
        "agent_speaks": "yes, by the same route in reverse",
        "needs": ["the did registered on the host", "an audio device or a null sink on the host"],
        "cost": "the phone is not in the call at all, which is only a cost if a flow insisted on hardware",
        "state": "designed",
    },
    "phone-taps-answer": {
        "what": ("the app on the phone rings, a full screen intent lights the panel, and our tap_text presses "
                 "answer on the call screen"),
        "agent_hears": ("no. the voice goes to the phone's own earpiece and mic, and there is no supported adb "
                        "path that turns call audio into something a process reads: screenrecord carries no call "
                        "audio and a capture needs the app or root"),
        "agent_speaks": "no, for the same reason, and tts into the phone's mic is a separate device we cannot reach",
        "needs": ["the app registering the did", "android doze whitelist and a foreground service",
                  "an unlocked screen for the tap"],
        "cost": "the ringing is solved and the conversation is not: an agent that presses answer has joined a call it cannot hear",
        "state": "designed",
    },
    "our-own-app-in-a-room": {
        "what": ("an app we write registers the did and also joins the livekit room the meeting rail already "
                 "describes, so the call audio is published where the agent can subscribe"),
        "agent_hears": "yes, through the room rather than the handset",
        "agent_speaks": "yes, publish tts into the same room",
        "needs": ["an app we ship and sign", "the room keys", "the sip leg inside that app"],
        "cost": "this is a client to build and maintain, not a verb to call, which is why it is named and not claimed",
        "state": "designed",
    },
}


def answer_paths():
    return [{"name": n, **r} for n, r in ANSWER_PATH.items()]


def answers_with_audio():
    """the shapes where the agent can both hear and be heard."""
    return [n for n, r in ANSWER_PATH.items() if r["agent_hears"].startswith("yes")]
