# mobile

*the phone as a device, and where the number is allowed to live on it*

a number proves a line. it does not prove a device, and a growing set of flows ask for the second thing: a signed verdict about genuine hardware, a sim, sensors that cannot help telling the truth, sometimes a camera. no sid and no did will ever answer that, which is why there is a phone in this story at all.

this branch holds two things apart that are easy to blur. **the device** is a phone we own, android over adb or an iphone on a desk. **the line** is the did that `main` already registers on a host. a phone is a second machine, and one did is one registration, so "put the number on the phone" is not a second line. it is either a race between two machines or a decision about where a password lives.

`mobile.py` carries both halves as data, `bin/mobile` answers questions about them, and `tests/selftest.py` pins the page to the tables.

## why a number is not a device

| what a flow sees | a did answers | a phone we hold | a guest phone |
| --- | --- | --- | --- |
| `sms-code` | yes, unless the sender refuses voip ranges | yes | yes |
| `device-attestation` | no | yes, on genuine hardware | no |
| `sim-presence` | no | yes, physical or an esim we keep | only as a story |
| `sensor-tells` | no | yes | no |
| `camera` | no | by hand, not by automation | no |
| `unlabelled-control` | no | android yes, ios no | android yes, ios no |

the first row is already `main`'s job and that is where it stays: a number on a host receives a code. the interesting row is the second one, because it is the class of check that a better number can never win. a voip did is refused by name by a lot of senders, and the flows that go further are asking whether the thing holding the account is a phone rather than a process. the answer only exists if a phone exists.

## what an agent can do to a phone that has no dom

a phone has no dom, and this is the sentence worth keeping: the closest thing is the accessibility tree, android dumps it over adb, and that is why four verbs are enough there. ios keeps the tree inside the phone, so mirroring gives pixels and ocr reads them. one platform has an api, the other has a camera.

the four verbs are `open_app`, `tap_text`, `type_text` and `screen`. they are borrowed from [phone-harness](https://github.com/phone-harness/phone-harness)'s local mode (mit), because they are the right four and because the half worth taking is the half that drives a phone you actually own. a device somebody else holds is a different argument, and this branch is not making it.

| backend | verbs | what it covers |
| --- | --- | --- |
| `android-adb` | all four | our own android guest, or a real android over usb or wi-fi |
| `ios-mirroring` | `screen` only | our own iphone, mirrored on a mac |
| `ios-guest` | none | a simulator, which has no springboard to tap and no verdict to offer |

`tap_text` refuses to run without a dump, and that refusal is the point: a tap without a dump is a guess with a screenshot attached. `find_node` is pure, so the parsing half of a tap is testable with no phone near it, which is why the suite has a tap test that needs nothing but an xml string.

## where the number goes: five routes, one decision

| route | where the sip secret ends up | survives the phone dying |
| --- | --- | --- |
| `host-holds-the-line` | the host, where it already is | yes |
| `app-registers-the-did` | the phone's sip client config | no |
| `provision-onto-phone` | the phone, pushed over adb | no |
| `termux-ssh` | the phone, wherever the shell writes it | no |
| `phone-holds-the-account` | a session, not a password | no |

### the one this branch would pick

`host-holds-the-line`. the phone is needed for the device checks, never for the ringing, so the number stays registered where it already is and the phone never holds a sip password. a secret that never reaches the phone cannot leak from it, and a guest that dies does not take the line with it.

the route is not a compromise, it is the shape the two halves want. the host is awake whenever an agent is doing anything at all, and the phone is only woken when a flow insists on hardware.

### putting the did on the phone instead

`app-registers-the-did` is real and sometimes right: a phone that rings the number itself, while the app is awake, needs no host in the path. it costs the thing this repo refuses everywhere else, which is a long-lived sip password sitting inside a machine that gets thrown away. if the phone is the owner's own and stays, the cost is fair. if the phone is a guest that is recreated per task, the password has to be re-issued every spawn, and that is a job nobody wants.

`provision-onto-phone` is the same placement with less typing: the config is pushed over adb and the app reads it on next launch, so no human types a password on a screen. it removes the human, not the exposure.

### whether the screen lights up, which is a different question

a phone that registered is not a phone that rang. three answers, and only one of them is ours to force:

- **an android app.** the invite can light the panel, because an incoming call is still one of the few cases android allows a full screen intent, drawn over the lock screen. the invite is the part that goes missing: doze parks the app's network, so the carrier goes on believing the registration is live while nothing reaches the phone. on a handset we control, `svc power stayon` while plugged and `dumpsys deviceidle` make that failure rare and visible, at the price of a phone that behaves like a desk terminal.
- **an iphone.** no. ios suspends the app and closes the socket within seconds of the screen locking, so the registration is gone long before a call arrives. the ringing that does work is pushkit plus callkit, which means the system draws the call screen and the sender is a push service rather than this branch.
- **the carrier's own forward.** yes, always, because the handset's telephony stack answers instead of an app. it costs the thing that made the phone useful here: a person picks up, and the agent is no longer the callee.

so `registered is not ringing`, and that is one more reason the recommended route keeps the line on the host: an awake host is something we have, and an awake phone is something we can only ask for.

### waking it on the ring, and then who actually answers

two questions live in the sentence "can the agent take the call", and only the first one is a wake problem.

**waking it is solvable on a phone we own.** whitelist the sip app from doze (`adb shell cmd deviceidle whitelist +<pkg>`), let it hold a foreground service, and an incoming call is one of the few things android still lets draw over a locked screen with a full screen intent. the invite lands, the panel lights, the answer button is there and `tap_text('Answer')` is a verb we already have. on an iphone it stays no: a suspended app cannot wake itself, the wake has to be a pushkit notification with an apns key and the app's own entitlement, and the call screen is system ui we only ever see as pixels.

**answering is the harder half, and waking does not touch it.** three shapes, and the agent only gets ears in two of them:

- **the host softphone answers.** baresip or pjsua as a process on the host, media to a local device or a file. the agent hears, speaks, and the phone is not in the call at all. `designed`.
- **the phone taps answer.** real, and it produces a call the agent cannot hear: the voice goes to the handset's own earpiece and mic, and there is no supported adb path that turns call audio into something a process reads. screenrecord carries no call audio and a capture needs the app or root. so this row answers the ringing and not the conversation. `designed`.
- **an app we ship that joins a room.** register the did inside it, answer there, and publish the media into the same livekit room the meetings rail already describes, so the agent subscribes the way it would in any other room. this is the shape that actually makes a phone answerable, and it is a client to build and keep, which is why it is named and not claimed. `designed`.

so the honest order is: the host answers, the phone is hardware, and the phone answers only once there is a client on it that can put the voice somewhere we can reach. waking it is the cheap part.

## the client, and which shape gets built first

the answer table above ends on a client, so here is the client: `client.py` carries two shapes, five components and the contract a build has to be wrong against, and `bin/mobile client` prints all of it with the steps in order.

**the host bridge goes first.** baresip holds the call on the machine that already holds the did, pipewire gives a headless host a mouth (a null sink, remapped as the microphone) and an ear (the same sink's monitor, recorded in segments on voice activity), and the room is skipped entirely unless the agent's brain runs somewhere else. no phone, no signing identity, no app store, and the first thing it proves is a real call to a real handset. the honest cost is that pipewire is the part this branch's suite cannot test, so the shape is written and unproven.

**the phone app comes second.** one android app with a sip leg and a room leg in the same process, ringing through the full screen intent the wake table already describes, publishing its microphone and playing the agent's track into the earpiece. it is the only shape where the phone is the callee and the hardware checks come from the same app, and it is the shape that needs an android toolchain, a signing identity and a device, none of which this branch has.

both refuse the same three things in the same words: the agent never subscribes to the mouth it publishes, nothing records unless the room was told, and the first turn of every call says what the caller has reached. a client that gets those wrong is not a client this repo would ship, whatever its latency.

### the shell on the phone, which is the idea worth answering

a shell on the phone over ssh is a real door, and termux is how it opens. the honest answer is that it is not the door we need: what is missing is pressing things in apps, and adb already presses. ssh earns its place for moving a file, and `adb push` already moves files. so it stays in the table as a considered route rather than a recommendation, and if a device ever arrives where adb is not available, that row is where the work starts.

## what a guest phone cannot do, and why that is the point

`device-attestation` is computed from hardware keys, so a guest cannot answer it and cannot be taught to. `sensor-tells` catches the rest: fixed sampling rates with no noise floor, a software renderer in the gpu string, `test-keys` in the build props, a sim whose country and network geography disagree. those checks exist in the spawnables device work, and they fail a guest on purpose rather than making it lie better.

the conclusion is not that guests are useless. it is that a guest is the wrong device for the specific job of proving hardware, and recognising that early is cheaper than discovering it at a verification screen.

## refused

- **a borrowed identity.** a device somebody else owns may be driven and may not become the identity.
- **attestation fiction.** a guest reporting genuine hardware is the one lie this branch will not build, because the verdict is signed and faking it is the attack, not the workaround.
- **a secret in the burn lane.** a guest that dies takes a long-lived password with it, so that placement is refused as a default rather than offered as a convenience.
- **ocr pretending to press.** vision reads. a tap needs a coordinate somebody can vouch for.
- **a silent tap.** a tap without a dump is a guess with a screenshot attached.
- **camera pretending.** a flow that wants a face gets a person, not four verbs and a screenshot.

## the state, and the first honest proof

every route and every backend here is `designed`: the verbs are the ones phone-harness documents, the adb argv is the adb argv, and nothing on this branch has driven a phone yet. `verified` is reserved for a phone we own answering `plan('open_app')` and `plan('screen')` successfully, which is a small, cheap first proof and the next thing to do.

after that the honest order is: one app opened and one screen read on an android we hold, then a tap that came out of a real dump, then the same three on an iphone through mirroring where only `screen` is available, and only then a hardware check that a guest would fail.

`bin/mobile prove` prints that ladder with the argv attached, `bin/mobile --setup` is the whole branch as one object, and [docs/setup.md](docs/setup.md) is the same thing written for a person holding a phone, including the four acts that are theirs and what each failure actually means.
