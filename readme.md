# omni

*turn one number into the rest of the stack: every carrier people already use, in one place an agent can read*

this branch is the omnichannel half of heyphony, and it exists because a number is not a conversation. the number is one rail: somebody calls it, somebody texts it, and heyphony on `main` makes that handleable by a process. everything else people actually reach each other on is not the number, and that is what lives here.

if you are looking for the number, the inbox, the call log or the install, you are on the wrong branch. `main` holds all of that, and this branch depends on it rather than the other way around.

> **this line used to be called `comms`,** on the umbrella repo, and it is called `omni` here. the rename is the whole of the difference: same folders, same one-way dependency, same rule that a carrier is a carrier.

## what lives here

one folder per carrier, because a carrier is the unit of anything that can be documented, gated and refused in the same shape. the table is generated from `lanes.py`, and a test fails if the two disagree.

| lane | the carrier | intake | gated by | state |
| --- | --- | --- | --- | --- |
| `mail` | agentmail and carlyemail | svix signed webhook, or a plain header | `MAIL_WEBHOOK_SECRET` | contract |
| `imessage` | photon spectrum | v0 signed webhook | `IMESSAGE_WEBHOOK_SECRET` | contract |
| `whatsapp` | waha | hmac webhook, digits whitelist | `WHATSAPP_WEBHOOK_SECRET` | contract |
| `signal` | signal-cli, linked device or registered number | a local cli, no webhook at all | `HEYPHONY_SIP_DID` for the register path | contract |
| `telegram` | bot api, or an account | a webhook with a secret token header | `TELEGRAM_BOT_TOKEN` | contract |
| `slack` | events api | url verification answered first, then signed events | `SLACK_SIGNING_SECRET` | contract |
| `discord` | gateway watcher | a long lived socket, read only | `DISCORD_BOT_TOKEN` | contract |

**state is `contract` on every row, and that is the honest word.** this branch is a shape rather than a running stack: the lane data, the gates, and the prose that says what each one would do. no catcher listens here yet, no message has arrived, and a page claiming otherwise would be the one thing this repo does not do.

## the dependency runs one way

`omni` imports heyphony. heyphony imports nothing from `omni`, and a test on `main` enforces that, so the number stays packageable on a machine that has never heard of this branch.

that direction is not a style choice. the number is the thing that must work when everything else is a dashboard with no lanes behind it, and a telephony lane that quietly grew a dependency on an umbrella would be a telephony lane you could no longer install on its own.

## one envelope, so an agent reads one shape

every lane normalises to the same entry: an id, a channel, a direction, a sender, a recipient, a body, a timestamp, a thread, and the raw payload. the agent should not have to know that a whatsapp message arrived as an hmac signed json body and an imessage arrived over v0. it reads one shape, and the shape is the same one `heyphony open` already emits for texts and voicemail.

the envelope is also where the refusals live. a payload that cannot be normalised is stored with its raw bytes and a reason, never dropped, because "the webhook fired and we could not read it" is a fact worth keeping.

## the two rules every lane inherits

### unset means closed

no lane opens because a secret is absent. an empty environment closes the route rather than opening it, which is the opposite of the convenient default and the reason a misconfigured deployment leaks nothing.

### a room is not somebody asking

groups are never whitelisted and a channel message is never treated as a question addressed to the agent. a monitoring lane with a mouth is a spam bot, and most of the lanes here answer only people who wrote to the agent directly.

## how a lane gets added

a folder, a readme, and a `LANE` dict in `<name>_lane.py` carrying the same five facts as the table: the carrier, the intake shape, the gate, the state, and one sentence of scope. the registry discovers folders rather than reading a list, so a lane that is not in the table is a test failure rather than a silent omission.

## what this branch is not

**not a second telephony stack.** everything about the number stays on `main`, including the sip config, the registration and the send rail. if a carrier here needs the number, it borrows it.

**not a bridge that invents rails.** where a carrier has no api worth using, the page says so and the lane closes. there is one deliberate exception in the shape: a linked device needs no number at all, and that is written down rather than discovered later.

**not finished.** seven rows, all contracts, no catcher. the next honest step is one lane end to end, not seven half-wired ones.
