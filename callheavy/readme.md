# callheavy: our own calls, arranged around a task

*main owns the number. this branch is where it dials, and where a call stops being a script and becomes a job with an answer*

main is a number, an inbox, and the rails a number unlocks, and it is inbound first on purpose. this branch adds the outbound half using **our own stack**: the registration the package already knows how to make, `baresip` on the host as the client, and the audio rails the umbrella already chose. the default rail hands a call to nobody: it rings from this machine, and no key is read. there is one other rail, `--via calle`, which asks call-e's hosted service to make the call with a key the owner brings, and it is chosen on every call and never by default.

what it borrows is an idea rather than a service. [call-e](https://heycall-e.com) is the tool that made "a goal, the fields to bring back, an answer you can act on" feel like the obvious way to do a phone call, and their developer docs (MIT, in `CALLE-AI/call-e-integrations`) describe the shape cleanly enough that a local implementation can follow it: a goal, a structured result, and a caller that keeps polling until the answer stops being pending. that vocabulary is used here, credited here, and produced by our own client and our own reasoning. **their dialler is not in this path.** an agent using this branch places a call from your own registration, and the only traffic that leaves the machine is the call itself.

## our own calls, on our own client

the client is baresip because it is the one the package already picked, and because its `ctrl_tcp` module is a json socket rather than a screen to scrape. but a socket is not a dialler, and getting from one to the other took reading the source rather than a blog post, which is why the next two sections exist.

### the config, and the two modules nobody mentions

`callheavy host` writes baresip's two files, and it writes them explicitly because the shipped example is subtly incomplete for this purpose:

- **`ctrl_tcp.so` is in the example and commented out.** a host that installs baresip from a distro and never uncomments it has no socket at all, and the failure looks like a client bug rather than a missing module.
- **the call verbs live in `menu.so`, not in the core.** `dial`, `hangup` and `answer` are registered by the menu module (`modules/menu/static_menu.c`), while the core command table has three entries: quit, insmod, rmmod. so a socket with no menu is a socket that answers nothing worth asking.

both are written as loaded modules with a comment saying what each one is for, and a test reads the written file back to check that the modules it needs are actually in it.

the control socket binds **loopback, not `0.0.0.0`**. the example config listens on every interface, which for a socket that can dial and hang up means anyone on the same wifi can place calls on your number. `127.0.0.1:4444` is the whole fix and it costs nothing.

the accounts file carries the sip password, so both files are written mode 0600, and a host that is a sentence rather than a hostname is refused before it reaches the file (`looks_like_host` in the package already learned that lesson once).

### the socket, spoken the way the source says

read out of `modules/ctrl_tcp/ctrl_tcp.c`, not from memory:

- a command is `{"command": ..., "params": ..., "token": ...}` and **`params` is a string**. the module's own example is `{"command": "dial", "params": "sip:alice@atlanta.com"}`.
- a response is `{"response": true, "ok": bool, "data": "...", "token": "..."}`.
- an event is `{"event": ..., "class": "call", "type": "CALL_CLOSED", "param": "...", "peeruri": ...}`, where the event names come from `bevent.c` (`CALL_INCOMING`, `CALL_RINGING`, `CALL_ESTABLISHED`, `CALL_CLOSED`).
- the module writes `"event": true` as a **string** in its own documented example while `response` is a boolean. the reader accepts both, because the example is the contract and it is inconsistent with itself.

framing is netstring on the way in (`netstring_insert` in the read handler) and the module reserves `NETSTRING_HEADER_SIZE` bytes before every json it sends. so this writes netstrings, reads netstrings, and also accepts a bare json object, because a reserved header that nothing fills is a shape that parses, and a stranded lane is worse than a tolerant one.

what comes back is what the client saw: accepted or refused, ringing or not, established or not, and how long the call was on our side of the wire. **the carrier's record is the authority on billing**, and the page says so where the code does.

### the audio, which is where a call actually fails

a call that connects and is silent sounds like a network problem and is almost always a capture device. so the audio is a first class part of this branch rather than an afterthought:

- **a virtual microphone for a native client.** on linux, `pactl` gives an agent a sink and a remapped source (`agent-mic`) that baresip can read as a microphone. pipewire is MIT and speaks the same interface, pulse is LGPL-2.1.
- **a file as a microphone for a browser.** chromium's fake device flags mean a call in a page can hear a wav, with no device, no server and no obs in the loop.
- **macOS needs blackhole, which is GPL-3.0 and an install plus a reboot**, and **windows needs vb-cable, which is not oss at all**. both are named rather than rounded up to "supported", because the umbrella's rule is to say which link is not free.
- **livekit is the room rail, not the call rail.** when the other person is in a room, the agent joins as a participant and publishes a track; that is a different media path from a sip call, and `callheavy room` prints the gate (`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`) and refuses with the missing name rather than a traceback. the sdk is an optional import, so this module loads on a machine that has never installed it.

and the honest gap, said once, because the word *pumping* was doing two jobs. **the agent's ears and mouth on a sip call are built and tested.** `callheavy/src/pump.py` puts the agent's voice where baresip reads its microphone and records what baresip plays, through four pulseaudio null sinks (two per side, never one, because a sink whose monitor is also the microphone feeds the call's own playback straight back and saturates the capture). pulseaudio's null sink keeps its own clock, so it works on a machine with no sound card, which is the property the mobile branch measured and pipewire did not have. `callheavy/src/rig.py` starts two real baresip instances that call each other over loopback, and the suite carries a tone across that call in each direction. what it asserts: the far end's tone comes back to the agent within 12 percent of the level it was spoken at and for the length it was spoken, the agent's tone reaches the far end with the other direction's frequency at least a thousand times weaker, and a quiet line records silence. what it was measured at on one run, which is not a guarantee: levels within about 5 percent across four amplitudes, and a separation of tens of thousands.

**what is still not shipped is a different problem: the bridge between a sip call and a livekit room.** that is one participant holding two media clocks and two codecs at once, which is a project rather than a helper. what works today is the simple split: the call rides baresip and the agent's voice rides the pump, or the room rides livekit and the agent is a participant. pick the one that matches where the other person already is. turning the ears into a transcript is also not here, because that needs a speech model and this repo ships none.

## the task, which is the part call-e does better

a dialler places calls. a task says what the call is *for*, what to bring back, and whether the answer is good enough to act on. that distinction is worth the whole branch, so it is implemented as its own module with its own rules.

### a goal, and the fields to bring back

`--goal` is the sentence a person would say to a colleague. `--schema` is a JSON Schema object listing what to collect, and the supported subset is exactly what a call result needs: `type`, `properties`, `required`, `enum`, `description`, `items`, `additionalProperties: false`. `$ref`, `oneOf`, `anyOf` and `allOf` are refused *before* the call, because an extraction that half understands a schema returns something plausible and empty.

`--success` is how either side would know it worked. a task without one is not ready, and `clarifications()` says so in the same `{needs, flag, why}` shape the rest of the package uses, so an agent that only reads json can fix its own request.

### the answer is checked, not trusted

the extracted answer is run through a local validator for that subset before anybody sees it. if it does not survive, the envelope says so:

| result_status | when |
| --- | --- |
| `available` | the answer passed its own schema |
| `unavailable` | no answer, or one that failed validation (`result_invalid` with the offending paths) |
| `not_applicable` | the call never got far enough to have a business answer |

`call_outcome` is separate, and is a fact about the telephone: `completed`, `no_answer`, `busy`, `declined`. a call that connected and got nothing and a call nobody picked up are different failures, and collapsing them is how a lane starts lying to its caller.

those four words are borrowed from call-e's developer docs, deliberately: a caller that already reads one calling tool should not have to learn a second dialect. the values are produced here.

### the prompt is text, and it is testable

`callheavy prompt` builds the question we ask our own model about a finished call: the goal, each field with its description, the instruction to answer `"unknown"` rather than guess, and the transcript. deterministic text with no vendor in it, which means a test can pin it and a human can read it before trusting it.

## what this branch will not do

- **no hosted dialler by default, and none by accident.** `--via` is required on `plan` and `dial` and has no default, so a call goes to the hosted service only when the command says `--via calle`. even then nothing is sent without `--authorized`, `--run`, `HEYPHONY_CALL=allowed` and a `CALLE_API_KEY` in the environment, and the key is read from the environment and never from a flag, so it cannot land in a shell history. on `--via callheavy` no request leaves the machine except the call itself.
- **no otp.** a code read out over a call is a verification flow wearing a goal costume, and the package's own access page already refuses that lane for a voip number.
- **no lists.** one recipient, always. calling a list is a different product with different consent, and this branch is not it.
- **no claim that a call happened because the socket said ok.** accepted, ringing, established and closed are four different facts and the record keeps them apart.
- **no scheduled fleet.** baresip will happily take a second dial; this lane places one call that a person asked for.

## the commands

```
callheavy host --did +1555... --user ... --password ... --sip-host atlanta.voip.ms [--dry]
callheavy plan --via callheavy --goal "..." --to +1555... --schema want.json --success "..."
callheavy dial --via callheavy --goal "..." --to +1555... --schema want.json --success "..." --authorized me [--run] [--settle 45]
callheavy plan --via calle --goal "..." --to +1555... --schema want.json
callheavy dial --via calle --goal "..." --to +1555... --schema want.json --authorized me [--run] [--wait 600 | --no-wait] [--region GB]
callheavy status --via calle --id <call id>
callheavy cancel --via calle --id <call id>
callheavy mic [--wav voice.wav]
callheavy room
callheavy prompt --goal "..." --schema want.json --transcript call.json
callheavy result --schema want.json --result answer.json --transcript call.json
```

`--via` is required and has no default, because one of the two rails spends credits. `callheavy` rings from this machine through baresip and wants a `--success` line, because we do the extracting ourselves. `calle` asks their hosted service, wants no `--success` because the service extracts, and wants a closed flat schema of at most 32 string, boolean, integer or number fields, which `plan` checks before a key is spent. a hosted call reads `CALLE_API_KEY` from the environment, needs `HEYPHONY_CALL=allowed`, and sends one request with an idempotency key derived from the call, so a retry after a timeout cannot place a second one. `--no-wait` returns the call id at once and `status` picks it up later. `cancel` is gated the same way, because it changes a call that costs money. both rails return one shape (`via`, `status`, `call_outcome`, `result_status`, `result`, `transcript`, `error`), and the own rail says plainly that its `result_status` is `not_applicable` and why. `plan` dials nothing. `dial` without `--run` is a plan too, and with it the phone rings, which is why `--authorized` is required and written into the record next to the call. records land in `~/.local/share/telephony/callheavy/` at mode 0600, beside the inbox rather than inside it, because the package's calls view reads the client's own sqlite and this is a different record of a different kind of fact.

## what is proven, and what is not

verified from source: the command, response and event shapes, the event names, the netstring framing, the two modules that are easy to miss, the config keys, and the accounts line format. pinned by tests: the payloads, the refusals, the validator, the envelope states, the loopback bind, the 0600 writes, the socket parse on both documented examples, a full dial against a fake transport, and the whole hosted client against a recorded copy of call-e's published contract.

**proven on a real call, on a machine with no sound card and no carrier:** two real baresip instances call each other over loopback, and this branch's own `dial.py` drives the real `ctrl_tcp` socket. it gets accepted, ringing at a few milliseconds and established at 2.04 seconds (that figure is baresip's two second auto answer delay on the stand-in, measured identically over four cold starts), reports the four facts separately, and `hangup` ends the call. the framing, the token matching and the event classification, which were written from baresip's source and only ever run against a fake, held against the real thing. the audio pump then carries a tone across that call in each direction (see the gap paragraph above), and the suite runs all of it on every pass, skipping by name on a machine without pulseaudio or baresip's pulse and ctrl_tcp modules rather than passing empty.

**not proven, and this is the part that matters:** a call over a carrier. everything above is two programs on one machine, g711 over loopback rtp. there is still no registration here, no did, no nat and no real handset, so what a carrier does to the call (codec negotiation, early media, a busy signal that is really a fast busy, the first second of audio that nobody hears) is untested. the first real test is one call to your own phone with `--settle 60` and a schema that asks whether the call was answered. the hosted rail has never been called with a real key: it is proven against the contract and a local stand-in server, and a live `--via calle` call has not been made, so what their service returns for a schema this client accepted is unknown until one is. the mac and windows audio rows are the first thing to check on real hardware, and both say `verified: false` in their own data rather than in a sentence.

## the files

```
callheavy/readme.md      this page
callheavy/src/host.py    the two baresip files, including the modules nobody mentions
callheavy/src/dial.py    the ctrl_tcp socket, and what it actually reports
callheavy/src/audio.py   the virtual mic, the room gate, and the room bridge that is not shipped
callheavy/src/pump.py    the agent's ears and mouth on a sip call, through four null sinks
callheavy/src/rig.py     two real baresip instances and an audio server, to prove the pump without a carrier
callheavy/src/calle.py   the hosted rail: a client for call-e's api, on the owner's own key
callheavy/src/calle.contract.json   the facts of their openapi file this client depends on
callheavy/src/task.py    the goal, the schema, the validator and the envelope
callheavy/src/cli.py     one json object per invocation, no prompts
bin/callheavy            the shim, resolving its own symlink like the other one
tests/selftest.py        classes added to the package suite, run the same way
```

the only file this branch changes outside its own folder is `heyphony/theidea/calling.md`, where that page said the goal oriented rail was parked. the suite compares against main and fails if the fold-in starts editing the package anywhere else.

the task shape, the four state vocabulary and the schema subset are adapted from CALL-E's open developer documentation (MIT, `CALLE-AI/calle-docs`). the client, the audio rails and the reasoning are ours.
