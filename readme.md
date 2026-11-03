# omni

*turn one number into the rest of the stack: every carrier people already use, in one place an agent can read*

this branch is the omnichannel half of heyphony, and it exists because a number is not a conversation. the number is one rail: somebody calls it, somebody texts it, and heyphony on `main` makes that handleable by a process. everything else people actually reach each other on is not the number, and that is what lives here: nine lanes, one envelope, and a catcher that verifies a signature before it parses anything.

if you are looking for the number, the inbox, the call log or the install, you are on the wrong branch. `main` holds all of that, and this branch depends on it rather than the other way around.

> **this line used to be called `comms`,** on the umbrella repo, and it is called `omni` here. the rename is the whole of the difference: same folders, same one-way dependency, same rule that a carrier is a carrier.

## what lives here

one folder per carrier, because a carrier is the unit of anything that can be documented, gated and refused in the same shape. the table is read out of the `LANE` dicts, and a test fails if a folder and its row disagree.

| lane | the carrier | intake | gated by | state |
| --- | --- | --- | --- | --- |
| `email` | agentmail and carlyemail | signed webhook, or smtp for the outbound leg | `CARLYEMAIL_SIGNING_SECRET`, `HEYPHONY_MAIL_SECRET` | designed |
| `imessage` | photon spectrum | v0 signed webhook, verified against the raw body | `PHOTON_SIGNING_SECRET` | designed |
| `whatsapp` | waha | hmac webhook, sha256 or sha512, digits whitelist | `WAHA_HMAC_KEY` | designed |
| `signal` | signal-cli, linked device or registered number | the linked device's own message stream | `SIGNAL_CLI_URL` | designed |
| `telegram` | bot api | a secret-token header, then signed events | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` | designed |
| `slack` | events api | url verification answered first, then signed events | `SLACK_SIGNING_SECRET` | designed |
| `discord` | gateway websocket, rest for replies | guild events and mentions, read only until addressed | `DISCORD_BOT_TOKEN` | designed |
| `meetings` | a browser in a spawnable, plus livekit for the audio | the room: speech, chat, transcript | `ZOOM_SDK_KEY`, `ZOOM_SDK_SECRET` | designed |
| `streaming` | rtmp ingest, obs for scenes | chat, where the platform's api allows reading it | `TWITCH_CLIENT_ID`, `KICK_STREAM_KEY` | designed |

two of those are not webhooks and the difference is worth keeping straight. the meetings lane joins a room instead of waiting for a post: zoom, google meet and teams, with livekit carrying the audio and screen sharing as the second rail, because a meeting is the one place the agent has to be present rather than reachable. the rcs fallback rides beside imessage as the floor under it, and streaming is the only lane that publishes, which is why a human presses go-live rather than a schedule.

## what actually runs here

`bin/comms` is the one command, and it is deliberately a shim over `python3 -m comms.cli` so the module is the thing you can read. it answers `setup` (the plan per lane, in lane order, with the gate each one needs), `status` (every lane and whether it is open), `inbox` (what arrived, from the number's own inbox), `serve` (the catcher), `card` and `recognica` (the contact book), and `doctor`. the lane-specific verbs hang off the same command rather than spawning nine binaries: `join` and `audio` for meetings, `watch` for the monitoring lanes, `go-live` for the one lane that publishes, `signal` for the linked device, `signup` for what an account needs before it will answer.

the modules are the ideas: `envelope.py` is the one shape and the refusal list, `gates.py` is the three signature schemes, `registry.py` finds folders instead of reading a list, `catcher.py` is the http routes and the store, `cards.py` is this repo's front door to the contact book, `signup.py` is what a carrier wants before it will talk, and `audio.py` is the microphone story per room.

turnkey is the ambition here rather than the current state, and the two words are worth separating: one command, one plan per lane, one gate each, and `designed` on every row until a message actually arrives.

four states, defined once in `envelope.py` and used everywhere:

- **verified** one real message arrived and was stored, and the evidence is named
- **designed** the gate and the payload shape were read from the carrier's own documentation
- **closed** the secret is unset. unset is closed, never open
- **refused** a real blocker stands, and wiring will not remove it

every row here sits at `designed`, and that is the honest word: the shapes are read from source, and nothing in this list has received a message yet. the moment one arrives and is stored, that lane moves to `verified` and the page says which one.

## the dependency runs one way

`omni` imports the number. the number imports nothing from `omni`, and a test on `main` enforces that, so the number stays packageable on a machine that has never heard of this branch.

that direction is not a style choice. the number is the thing that must work when everything else is a dashboard with no lanes behind it, and a telephony lane that quietly grew a dependency on an umbrella would be a telephony lane you could no longer install on its own.

the dependency shows up as exactly one call, in `comms/number.py`: the inbox a message is stored in belongs to the number. the import is lazy, because a lane's gate and signature are this branch's own business and only storing a message needs the other half to be there. it resolves two ways, in the order a reader would try them: `heyphony.src` when the package tree is on the path, and `src` when this branch is sitting inside a heyphony checkout. when neither is there the error says so at the moment a message arrives, naming both routes, instead of failing at import time when nothing has been asked for yet.

## one envelope, so an agent reads one shape

every lane normalises to the same entry: an id, a channel, a direction, a sender, a recipient, a subject, a body, a timestamp, a thread, a reply-to and the raw payload. the agent should not have to know that a whatsapp message arrived as an hmac signed json body and an imessage arrived over v0. it reads one shape, and the shape is the same one `heyphony open` already emits for texts and voicemail.

the envelope is also where the refusals live. a payload that cannot be normalised is stored with its raw bytes and a reason, never dropped, because "the webhook fired and we could not read it" is a fact worth keeping. and the refusals themselves are a fixed list rather than a judgement made per lane: a voip did is not a verification channel, texts do not arrive over sip, a group is never whitelisted, a monitoring lane does not get a mouth, and no official api means no lane rather than a scraper in borrowed cookies.

## the card, so nobody pastes a chat again

the reason this branch exists for a human and not only for a process: the same person writes on five carriers under five handles, and an agent that treats those as five strangers is an agent you have to brief five times.

this is the one memory the branch promises, and it is not a shared inbox with a hundred unread in it: it is the same person, recognised across lanes, readable in one order.

a card is one person, every lane they use, and a note. `bin/comms card` links a handle to a card, refuses to link a handle that already belongs to somebody else rather than silently merging two people, and `--digest` prints the last exchange across every lane in one order, which is the paste a human does by hand before they ask "what did sam want". an unknown sender is stored, not stitched: a stranger becomes a card when a human says so.

the contact book underneath it is `comms/recognica/`, and it keeps three shelves rather than one list, because an owner, a person and another agent are not the same kind of entry: see [comms/recognica/readme.md](comms/recognica/readme.md), with the shelves at `comms/recognica/humans/owner/`, `comms/recognica/humans/people/` and `comms/recognica/agents/`.

## the two rules every lane inherits

### unset means closed

no lane opens because a secret is absent. an empty environment closes the route rather than opening it, which is the opposite of the convenient default and the reason a misconfigured deployment leaks nothing.

### a room is not somebody asking

groups are never whitelisted and a channel message is never treated as a question addressed to the agent. a monitoring lane with a mouth is a spam bot, and most of the lanes here answer only people who wrote to the agent directly.

## how a lane gets added

a folder, a readme, and a `LANE` dict in `<name>_lane.py` carrying the facts the table shows: the carrier, the intake shape, the relay, the gate, and the state. the registry discovers folders rather than reading a list, so a lane that is missing from the page is a test failure rather than a silent omission.

## what this branch is not

**not a second telephony stack.** everything about the number stays on `main`, including the sip config, the registration and the send rail. if a carrier here needs the number, it borrows it, and texts are caught by the number rather than by this catcher.

**not a bridge that invents rails.** where a carrier has no api worth using, the page says so and the lane closes. there is one deliberate exception in the shape: a linked device needs no number at all, and that is written down rather than discovered later.

**not verified.** nine lanes, all designed, and no message has arrived on any of them. the next honest step is one lane end to end, not nine half-wired ones. [docs/setup.md](docs/setup.md) carries the steps that used to be implied, and it stops before spending money because no payment rail is wired here on purpose.
