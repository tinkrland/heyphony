# heyphony

*a jerryrigged workaround for giving your ai agent a phone number of its own, one you can actually reach*

there is no product that sells a phone number to a program. there are products that sell a phone number to a company that happens to have an ai agent, at a markup, behind a dashboard nobody's risk engine reads. this folder is the other route: a number bought for about a dollar, registered to a client on a host you already run, with a cli in front of it so the thing that answers is a process and not a person.

that is the whole pitch, and it is smaller than it sounds. your agent ends up with a **phone number of its own**, in the same network as every other number, dialable and textable from the phone already in somebody's pocket. everything else here is plumbing to make that address handleable by something without eyes.

> **this copy is the standalone package.** these pages were written beside the umbrella, so a few of
> them name sibling lanes (signal, email, meetings, the contact book) that live in
> [spawnables on the comms branch](https://github.com/tinkrland/spawnables/tree/comms) rather than in this
> repo. the argument holds and the code runs without them: what leaves this package is the number and
> the rails a number unlocks, and nothing here imports the umbrella.

if you opened this folder and could not tell how it runs, that is what [directory.md](directory.md) is for: the folder tree, the setup flow and the manage flow drawn separately, and where each command sits. the rest of this page is the argument for the shape, not the map of it.

## the problem

the first problem is that a phone number is a weird object to give a program. it is not a url, it is not a key. it is a lease on a slice of a network that was designed in the seventies, sold through portals written in the two thousands, and answered by an endpoint that has to keep a tcp connection alive. the two obvious answers both fail. you can rent an "agent phone" from a startup, which is a sip did with a nicer invoice and a claim about ai you cannot verify. or you can build telecom, which is a decade of work about interconnection agreements before you have received a single text.

the second problem is quieter and it is the one that decides the design: the interesting half of telephony is *receiving*, and receiving is cheap. a text is a provider event. a voicemail is a carrier feature. both of them sit somewhere that is not you, waiting, whether or not anything in your rack is awake. sending is the half with consequences, and the half that gets a number blocked, and the half most agent telephony pitches are actually selling. so a lane built for an agent that mostly gets messages and occasionally answers one is a different shape from a call centre, and most of the honest limits in this folder come from taking that difference seriously instead of pricing around it.

## the point

one number, ringing a process instead of a handset. calls arrive and become a call log, texts arrive and become a message, voicemail arrives and becomes a file, and all three land somewhere an agent can read without a mail client, a softphone or a pair of eyes. that is what you get.

what it gives you, turnkey, is small and specific: a did from a provider that sells them for about a dollar a month, registered on the **host** so the number is alive whether or not any guest is running. an inbox with the three things a mailbox gives a human for free and an agent never gets, which are a stable handle for a message, an answer to "is this new", and a cheap way to read one item in full. a setup a process can perform rather than a wizard it has to watch. and once the number exists, one command per rail that only ever wanted a phone in the first place.

nothing here asks you to write a webhook handler, sign a payload by hand, or keep a container warm so a text can arrive. and the folder packages alone: take it, put it on a host with a number, and it works without the rest of the branch, because the umbrella depends on it rather than the other way round.

### the number outlives the machine

the honest shape of a phone number is that half of it is somebody else's computer, so the interesting question is not what happens while everything is up. it is what happens when the host is asleep.

|               | phone calls | text messages |
| ------------- | ----------- | ------------- |
| **device on**  | rings the client on the host, and becomes a call in the log (recorded and transcribed when the rail is wired) | the provider's webhook lands in the shared inbox, one message |
| **device off** | no registered endpoint, so the carrier decides: voip.ms answers with its own voicemail and emails it, flowroute has no fallback and the caller simply gets nothing | still arrives, because texts never travel over sip: the provider webhook stores it, or the carrier emails it, and the agent reads it when the machine is back |

that asymmetry is the whole design of the lane, and it is why the number lives on the host rather than inside a burnable guest. a did is one registration, so a second machine registering it is a race rather than a second line. the sip password is long lived, and a guest we intend to shred would copy it and then need a fresh secret every spawn. and a number that only rings while a guest happens to be up is dead in exactly the case that matters most, which is idle at three in the morning. guests read the inbox over the control plane and never hold the provider credential, which is the rule every other secret in the branch follows too.

### the setup is a cli, so an agent can operate it

`heyphony setup select sip` walks the questions this actually needs, as menus rather than paragraphs.

```
$ heyphony setup select sip
  which provider (all of them about a dollar a month or less):
  > voip.ms    carrier side voicemail and texts land in email, so the inbox keeps
               working with the machine off
    flowroute  texts by webhook or smpp, no voicemail fallback
    anveo      the one provider whose whole chain is scriptable, sms on us/ca/uk
    ...
  does this number already exist?
  > i already have a sip did   paste the number, then the sip username and password
    get a new one              order it: from the cli where the api allows, otherwise a portal
```

every one of those questions is also a flag, because the caller is often not a person, and a menu that only exists as a menu is a wall. a run with no terminal and no flags **returns the next question instead of waiting for an answer**: `{"needs": "provider", "flag": "--provider", "options": [...]}`. nothing blocks, nothing hangs, and a missing answer is a value rather than a stuck process.

the plan that comes back is the whole errand, not just the connect line: what to order, where to point its texts, which voicemail to expect, and the two commands that prove it works. the parts a person still has to do are marked as such rather than dressed up as automation. ordering is a browser act for every provider except anveo, and the payment step stays a person's for all of them, including anveo, because a purchase is a purchase.

### text first, because receiving is the cheap half

the lane is inbound first on purpose. receiving is cheap, patient and useful: a number that rings a process, a voicemail that becomes a file, a text that is already waiting when nothing was awake to answer it. sending stays narrow and at human pace, one message at a time, never a campaign.

texts are the patient channel and the one worth building first, because they are provider events rather than media streams. voicemail is patient because it is a carrier feature, which is why it only shows up when the provider has one, and why one provider's silence in that column is a fact rather than an oversight. live calls are the impatient channel and are supported rather than central; [the calling page](theidea/calling.md) says what that means and which rails are parked.

### ten providers, and one question that sorts them

the number shops fall into two piles, and the pile is decided by a single question: when somebody texts this number, does anything arrive, and can a process read it. seven of the ten answer yes, three answer no, and the three that answer no are listed anyway because "i sell eu dids" is not the same sentence as "i can be your inbox".

`heyphony hooks <provider>` prints the thing to paste, the steps around it, and for the ones with a real api the exact call that sets it, and `--apply` makes that call when the credentials exist. the full table, the per-provider offline matrix, and the two corrections we owe ourselves are in [vendors](theidea/vendors.md), which is the page to read before choosing.

### the client, decided

the host runs **baresip**, because its `ctrl_tcp` module is a json command socket: json in, json out, `"command": "dial"`, and an event bus back, all of it visible in the module's own source with `ctrl_tcp_listen 0.0.0.0:4444` sitting in the shipped config example. a typed protocol an agent speaks beats a cli a parser has to read, and this lane mostly needs three things, which are dial, hear, and hang up.

pjsua was the other candidate and lost on weight: the pjsip media stack plus pjsua2 bindings built per host, and an interactive telnet console instead of a socket. the verdict lives in `src/linphone/sip.py` as data with the reasoning attached so it does not get relitigated from vibes in six months. linphone still does the desktop job fine, and its configuration keys are what this folder generates.

### what a number is and is not

a did is voip, and voip numbers are widely refused by exactly the flows that most want a phone number: bank signups, a large share of consumer verification, messaging apps that verify by sms to the same number. that is a property of the number type, not of the provider, and no dashboard fee changes it. what the agent voice startups charge buys convenience, not a different class of number and not a better outcome at the sender's risk engine.

so the honest promises are short. a number that receives. a mailbox that catches while you sleep. calls that ring a process. what is not promised is an identity that passes a bank, and configuration does not turn a did into one. a did stays voip, refused for otp, refused for bulk outbound, and perfectly good for receiving.

## the idea, written down

the reasoning that did not fit in a readme lives beside it, on purpose, because a page that explains what something *is* should not also argue with itself.

- [epilogue, back to the basics](theidea/epilogue.md): the pbx that already solved this in 1998, the softphone nobody retired, and what mcgyvering a modern one actually meant here
- [vendors](theidea/vendors.md): ten number shops, what each one really does with a text, and which ones cannot be an inbox
- [onramp](theidea/onramp.md): the ramp for signal and whatever else only wants a phone, and the boundary between onramping a rail and becoming one
- [calling](theidea/calling.md): text first is not voice never, and the rails a call can ride
- [locale](theidea/locale.md): where a number is bought changes what it is, why six countries issue cloud numbers as mobiles and the +1 countries do not, and why that is law rather than a trick
- [glossary](theidea/glossary.md): did, sip, pstn, trunk, codec, catcher, getter, and the rest of the words
- [access](theidea/access.md): turnkey today, open source eventually, the licence question we have not answered, and the four planned surfaces
- [journal](journal/): the dated record of decisions, so six months from now the reasoning is still findable

## where it is honest about itself

nothing in here has placed a call yet. what is built and tested: config generation against linphone's own keys, call history and message readers against its own sqlite schemas, the provider table with works-while-offline as data, the sms catcher, the inbox, the guided setup with its flags and its menu, the getter recipes, a provisioning chain that stops before it spends money, and a local launcher that shows caught messages and voicemail as one thread with a person.

what proves it is one host, one did, an echo test, and `heyphony calls` seeing that call in the log.

```
heyphony setup                          # the whole plan, as json
heyphony setup select sip [--provider voipms|flowroute|anveo|...] [--did +1... | --new] [--json]
heyphony setup provision --provider anveo --areas --country-id US   # what is in stock, free
heyphony connect sip --voipms --did +1... --username ... --password ...
heyphony open messages|calls|voicemail|all
heyphony app [--port 8790]              # the launcher: tabs for caught messages, voicemail, calls
heyphony hooks <provider> [--apply]
heyphony get signal [--path phone-signup|link-desktop|register-number] [--run]
heyphony status | calls [--missed] | inbox | serve --port 8099 | doctor
```

licences: linphone (gpl-3.0, or agpl-3.0 for the sdk), baresip (bsd-3), and nothing here is agent only software. an agent is just another sip endpoint, sitting beside softphones, desk phones and an ivr that answers in a queue. which licence *this* ends up under is a separate question with a real constraint and no answer yet, and [access](theidea/access.md) is where it is argued.
