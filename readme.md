# heyphony

*give your ai agent a phone number of its own, one you can actually reach*

there is no product that sells a phone number to a program. there are products that sell a phone number to a company that happens to have an ai agent, at a markup, behind a dashboard nobody's risk engine reads. this repo is the other route: a number bought for about a dollar a month, registered to a client on a host you already run, with a cli in front of it so the thing that answers is a process and not a person.

it is also the turnkey version of the `heyphony/` folder that lives inside the comms branch of [spawnables](https://github.com/tinkrland/spawnables). same code, moved out of the umbrella and given its own front door, because a number is one did, one carrier and one long lived secret, and a package holding all three should not need an umbrella to stand up. the dependency runs one way and stays that way: comms depends on heyphony, heyphony imports nothing from comms, so what is here runs on a bare machine with a python on it.

everything below is the shape of the thing. the long argument for the shape is in [heyphony/readme.md](heyphony/readme.md), and the map of how it runs is in [heyphony/directory.md](heyphony/directory.md).

## what it gives you

**a number that rings a process.** calls arrive and become a call log, texts arrive and become a message, voicemail arrives and becomes a file, and all three land somewhere an agent reads without a mail client, a softphone or a pair of eyes.

**an inbox with the three things a mailbox gives a human for free.** a stable handle for a message, an answer to "is this new", and a cheap way to read exactly one item in full. a mailbox gives an agent none of these, which is why `heyphony open messages` exists and why read state lives in a sidecar instead of being invented from a payload that never says whether anyone looked.

**a setup a process performs rather than a wizard it watches.** every menu is also a flag, and a run with no terminal returns the next question as json instead of waiting for an answer that will never come.

**the rails a number unlocks, one command each.** signal wants a phone before it will talk to you, so `heyphony get signal` is the whole install. telegram is the second ramp, in two flavours, because a bot and an account are different creatures wearing the same name.

### the number outlives the machine

the honest shape of a phone number is that half of it is somebody else's computer, so the interesting question is what happens when the host is asleep. texts still arrive, because sms never travels over sip: the provider holds it and posts or emails it, and the agent reads it when the machine is back. calls do not, because a call needs a registration and a registration needs a host that is running. that asymmetry is the whole design of the lane, and it is why the number lives on the host rather than inside a burnable guest.

## get it

four ways, in the order most people want them. the full table with what each one needs is in [npm/readme.md](npm/readme.md).

```
curl -fsSL https://raw.githubusercontent.com/tinkrland/heyphony/main/npm/install.sh | sh
git clone https://github.com/tinkrland/heyphony && cd heyphony && ./bin/heyphony status
cd npm && npm pack && npm i -g ./heyphony-0.2.0.tgz
npx heyphony status          # the moment the package is published, which it is not yet
```

the url install needs neither node nor git, which is why it is first. nothing here is on the npm registry yet: the name `heyphony` is unheld, and `npm publish` from `npm/` is the whole ceremony when whoever owns this wants it there.

an agent installing this should read [npm/agents.md](npm/agents.md) instead of this page, because it says which four commands to run, which two questions are for its human, and what it is not allowed to attempt.

## three places it can live

the command is the same everywhere; what changes is which computer holds the registration, the secret and the catcher, and what happens to all three when that computer sleeps. there are three honest answers, and the `setup` branch of this repo is about the instructions for each: an agent on a local computer, where the answer depends on which computer, a computer of its own in a container or a cloud vm, and a spawnable guest from the spawnables line.

## this repo, and the rest of the lines

`main` is this page, the code, and the packaging. only `main` exists today, and the rest of the split is laid out rather than implemented. the rule that decides where a thing goes is whether it is the number or the conversation: `main` holds the number and the rails a number unlocks, `comms` holds the rest of the stack, and nothing crosses back.

| branch | what it is for |
| --- | --- |
| `main` | heyphony: the number, the inbox, the install |
| `comms` | everything that is not heyphony: the umbrella and the rest of the stack (mail, imessage, whatsapp, signal, telegram, slack, discord) |
| `omnimeetings` | the live half (google meet, zoom, teams), joining and speaking and sharing a screen |
| `makeacall` | goal oriented calling, with [heycall-e](https://heycall-e.com) integrated |

a number is useful on its own, which is why it gets the first branch and the working code. the other three are places to put the rest when they arrive, and saying they are planned is more honest than a folder with a readme and no lane behind it.

## the folder

```
heyphony/     the package: src/, providers/, journal/, theidea/, directory.md and the argument
bin/heyphony  the shim a clone runs, and the one install.sh links onto your path
npm/          the installable: package.json, the node shim, the bundle step, the url installer
tests/        the suite that holds the prose to the code
```

## what it will not do

a did is voip, and voip numbers are refused by exactly the flows that most want a phone number, so there is no otp story and no way to buy one. outbound is a draft, kept and not sent, because one message at human pace is a lane and a campaign is a different product with different obligations. and nothing here publishes: there is no stream to go live on and no account to create, only a number that can be reached.

those are not gaps waiting for a sprint. they are the limit of what a number of this type can do, and the pages that name them are the ones worth reading before asking for them.
