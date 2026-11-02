# heyphony

*a jerryrigged workaround for giving your ai agent a phone number of its own, one you can actually reach*

there is no product that sells a phone number to a program. there are products that sell a phone number to a company that happens to have an ai agent, at a markup, behind a dashboard nobody's risk engine reads. this repo is the other route: a number bought for about a dollar a month, registered to a client on a host you already run, with a cli in front of it so the thing that answers is a process and not a person.

that is the whole pitch, and it is smaller than it sounds. your agent ends up with a **phone number of its own**, in the same network as every other number, dialable and textable from the phone already in somebody's pocket. everything below is the argument for the shape and the way to get it.

> **this repo is the standalone package.** these pages were written beside the umbrella, so a few of them name sibling lanes (signal, email, meetings, the contact book) that live in [spawnables on the comms branch](https://github.com/tinkrland/spawnables/tree/comms) rather than here. the argument holds and the code runs without them: what leaves this repo is the number and the rails a number unlocks, and nothing here imports the umbrella. the dependency runs one way and stays that way.

if you opened this repo and could not tell how it runs, that is what [directory.md](directory.md) is for: the tree, the setup flow and the manage flow drawn separately, and where each command sits.

## telecom was built for people, and that is still the layer agents need

the interesting thing about the current moment is not that agents are new. it is that a large number of people have looked at the telephone network, decided it belongs to a previous era, and started rebuilding it for machines. this repo takes the other side of that bet, and the reason is not sentiment about copper.

### eighty years of infrastructure that already works

the public telephone network is the most thoroughly solved communication system that exists. a number is a routing entry that resolves anywhere on earth. a call is a handshake that works through routers, carriers, mobile networks and legacy switches that predate the web by decades. a text reaches a phone that has no app installed, no data plan and no idea what an api is. the pbx in the office closet and the softphone on the desk are the two ends of that same ordinary stack, and both of them have been operating at scale since before the people building agent frameworks were born.

none of that is fashionable, and all of it works when the far end is a human being with a phone in their pocket.

### the rewrite everyone is reaching for

the obvious move for a new era is a clean sheet: an agent native network, agent to agent protocols, a stack where both endpoints are programs, no legacy anything. it is a genuinely interesting line of work and some of it will become the standard. but it starts from a hard position, which is that it has no one on the network yet. a protocol for agents talking to agents becomes useful when agents are the thing that answers, and right now they mostly are not.

### the fact that changes the plan

look at what an autonomous agent is actually trying to reach when it picks up a phone. it is trying to book something, confirm something, chase something, cancel something, or ask a business a question. the far end of that call is a person at a desk, or a call queue, or an ivr that was installed in 2011. it is a human service, reached over the same cellular infrastructure everyone else uses, because that is where the humans are.

so the honest design goal is not "build telecom for agents". it is "make the telecom that exists handleable by something without eyes and without patience", and those are very different amounts of work.

### adapted, rather than invented

which is why heyphony is not ai native from scratch. it is ai adapted: it takes the brick and mortar pbx and softphone infrastructure that has been sitting there forever, and it changes what has to change for a process to drive it.

- **the config a human would type into a dialog** is generated from the client's own schema, written `0600`, on the host that holds the registration.
- **the socket a softphone never used** is the one an agent speaks: the client already exposes a json control channel, and the job was reading its source rather than guessing at a screen.
- **the inbox a mailbox gives a human for free** is rebuilt as files plus a sidecar, because a payload never says whether anyone looked.
- **the menu a person clicks** is also a flag, and a run with no terminal returns the next question instead of waiting for an answer that will never come.

meeting telecom at its level, as the current needs call for, is the whole approach. the network is not the problem, and replacing it is not the job. making it answer a process is.

### when agent to agent matures, that is a different lane

this is not a claim that a2a is wrong or unnecessary. it is a claim about ordering: the demand that exists today is agents reaching human services on the infrastructure the humans already use, and a number is how you get there. when the other thing arrives, it will be a different lane with a different shape, and this one will still be sitting on the same network as everybody's phone.

## the market splits the number in half

the other thing that pushed this repo into existence is quieter than the network argument, and it is about what is on sale. the offers are decoupled, and the coupling is the whole point of having a number.

### the two halves are sold separately

look at what exists for an agent that needs to be reachable and find yourself choosing between two products that each do half the job:

- **voice first.** services that assign a voip number to an agent so it can place and take calls. usually aimed at call centres and heavy outbound callers, and usually priced by the minute. texting is not part of the deal, because texting is a different meter.
- **text first.** ai texting services with an inbox, a thread and a reply, and no calling at all. some of them will not even give you the number, only a seat inside their product.
- **neither of them exposes the sip layer**, which is the thing that would let one number be both, because the sip layer is where the margin stops being theirs.

so an agent ends up with a voice number and a separate texting number, two identities for one human relationship, and no way to connect them.

### why an agent needs both on one number

a person does not have a calling number and a texting number for the same plumber. they call it, then they text it, and both arrive in the same thread of the same relationship. an agent that is supposed to behave like that has to do the same thing: read the call log and the message thread as one context, decide that the missed call and the text twenty minutes later are the same conversation, and reply on whichever rail the person actually used.

two numbers makes that impossible in a way that is not a bug you can fix later. the identity is split at the network, so no amount of cleverness in the inbox puts it back together.

### what we do instead

one number, registered to a client we run, with the sip layer in our own hands. the call log, the texts and the voicemail come from the same number, land in the same store, and the agent reads all three without asking which product they came from. that is why this repo is a client and a cli rather than a subscription: the hybrid you want is the thing a hosted product has to charge you twice for.

## what it gives you, turnkey

**a number that rings a process.** calls arrive and become a call log, texts arrive and become a message, voicemail arrives and becomes a file, and all three land somewhere an agent reads without a mail client, a softphone or a pair of eyes.

**an inbox with the three things a mailbox gives a human for free.** a stable handle for a message, an answer to "is this new", and a cheap way to read exactly one item in full. `heyphony open messages` exists for that reason, and read state lives in a sidecar rather than being invented from a payload that never says whether anyone looked.

### the setup is a cli, so a process can operate it

every menu is also a flag, and a run with no terminal returns `{needs, flag, options}` as json instead of blocking. `heyphony setup select sip` is the guided path a person uses, and `heyphony setup --provider voip.ms --did +1...` is the same thing with the menu skipped. nothing in this repo prompts and waits.

### what a number unlocks, one command each

signal wants a phone number before it will talk to you, so `heyphony get signal` is the whole install. telegram is the second ramp, in two flavours, because a bot and an account are different creatures wearing the same name.

### the number outlives the machine

the honest shape of a phone number is that half of it is somebody else's computer, so the interesting question is what happens when the host sleeps.

- **device on**: calls ring the host client, texts arrive through the provider's webhook into the inbox.
- **device off**: calls do not arrive, because a call needs a registration and a registration needs a running host. texts still do, because sms never travels over sip. voicemail depends on the carrier, and the per provider table in [providers/](providers/) says which carriers keep it for you.

that asymmetry is the design. it is why the number lives on the host rather than inside a burnable guest, and why receiving is the half this repo optimises for.

## get it

four ways, in the order most people want them. the full table with what each one needs is in [npm/readme.md](npm/readme.md).

```
curl -fsSL https://raw.githubusercontent.com/tinkrland/heyphony/main/npm/install.sh | sh
git clone https://github.com/tinkrland/heyphony && cd heyphony && ./bin/heyphony status
cd npm && npm pack && npm i -g ./heyphony-0.2.0.tgz
npx heyphony status          # the moment the package is published, which it is not yet
```

the url install needs neither node nor git, which is why it is first. nothing here is on the npm registry yet: the name `heyphony` is unheld, and `npm run preflight` then `npm publish` from `npm/` is the whole ceremony when whoever owns this wants it there. [npm/publish.md](npm/publish.md) is the runbook.

an agent installing this should read [npm/agents.md](npm/agents.md) instead of this page, because it says which four commands to run, which two questions are for its human, and what it is not allowed to attempt.

## three places it can live

the command is the same everywhere; what changes is which computer holds the registration, the secret and the catcher, and what happens to all three when that computer sleeps. there are three honest answers, and the `setup` branch of this repo is about the instructions for each: an agent on a local computer, where the answer depends on which computer, a computer of its own in a container or a cloud vm, and a spawnable guest from the spawnables line.

## the tree

the repo root is the tree, which is why the import path is `src.runner.cli` rather than something nested under a package folder.

```
src/          the code: providers, runner, linphone, setup, manage, onramp
journal/      explainers and dated notes
theidea/      the argument for the shape, including the limits
providers/    per vendor notes
directory.md  the map: setup and manage, drawn apart
bin/heyphony  the shim a clone runs, and the one install.sh links onto your path
npm/          the installable: package.json, the node shim, the bundle step, the url installer
tests/        the suite that holds the prose to the code
LICENSE       source available, bsl shaped
```

## this repo, and the rest of the lines

`main` is this page, the code, and the packaging. only `main` exists today, and the rest of the split is laid out rather than implemented. the rule that decides where a thing goes is whether it is the number or the conversation: `main` holds the number and the rails a number unlocks, `comms` holds the rest of the stack, and nothing crosses back.

| branch | what it is for |
| --- | --- |
| `main` | heyphony: the number, the inbox, the install |
| `comms` | everything that is not heyphony: the umbrella and the rest of the stack (mail, imessage, whatsapp, signal, telegram, slack, discord) |
| `omnimeetings` | the live half (google meet, zoom, teams), joining and speaking and sharing a screen |
| `callheavy` | goal oriented calling, on our own client rather than a hosted dialler |

a number is useful on its own, which is why it gets the first branch and the working code. the other three are places to put the rest when they arrive, and saying they are planned is more honest than a folder with a readme and no lane behind it.

## the licence, and why it is not mit

this is a source available licence, not an open source one: bsl shaped, with the permitted purposes of the functional source licence and the three hard prohibitions of the elastic licence. you can read it, run it, modify it, and ship your own agent on it, including in production. what you cannot do is take it and sell it as the thing it replaces, or strip the notices out of it.

each version converts to mit two years after it is released, and the table in [LICENSE](LICENSE) dates every version that exists. versions that are not listed have not been released.

## what it will not do

outbound is a draft, kept and not sent, because one message at human pace is a lane and a campaign is a different product with different obligations. nothing here publishes: there is no stream to go live on and no account to create, only a number that can be reached. and the number is a voip number, which is the type of number that the flows most likely to ask for one refuse, so there is no verification story here and buying one is not something this repo will do for you.

those are not gaps waiting for a sprint. they are the limit of what this kind of number can do, and [theidea/](theidea/) is where each one is argued rather than listed.
