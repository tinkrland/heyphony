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

### an answer, one message at a time

`heyphony send` exists, and it is the narrowest version of outbound that is still useful: one recipient, one body, drafted unless the gate is open and the call asks for it. a reply to somebody who wrote first is the case it was built for, and a loop over a list is the case it refuses.

### leaving a voicemail is the same act, with a voice

`heyphony voicemail --to +1... --message "..." --send` places **one** call and speaks a message you wrote. the pstn leg comes from your livekit trunk rather than from this repo, and the speaking half is a python worker (`livekit-agents`, apache-2.0) that heyphony writes to disk so you can read it, edit it and run it yourself: a call that only exists while some service worker is alive deserves to be visible rather than magic.

two things about it are worth saying plainly rather than discovering on the first call:

- **there is no answering-machine detection here.** livekit does not offer it and a naive attempt at it is how an agent ends up talking over a person. the plan waits a fixed number of seconds after the answer and then speaks. if a human picked up, a human hears the message. that is why `--wait` is a flag and not a promise.
- **a voicemail is not a call you can hold.** nothing here receives the far end's audio into a conversation, transcribes it, or dials back. it is one outbound leg with a spoken message at the end of it.

it is gated like the text rail: `HEYPHONY_CALL=allowed` and `--send`, both, or you get the plan printed in full.

### a group is four named people, not a list

`heyphony group new --name "dinner" --with ada=+1... --with bob=+1...` then `heyphony group say dining --text "seven o'clock"`.

the outbound rail refuses a pasted list, and that refusal is about broadcast: one text to many strangers at machine pace with no conversation behind it. a group chat is the other thing, so the shape is narrow enough that the difference is structural instead of a promise. four members is a hard ceiling rather than a flag, a member is a name **and** a number, and every message goes out through the same one-recipient rail with its own gate and its own character limit. one member failing does not quietly become "sent to the group".

### what comes back, and how a reply is answered

a member's reply arrives as an ordinary one-to-one text from their number, because that is the only kind of text this number can receive: we never started a carrier group, so nothing marks the message as belonging to one. `heyphony open messages` therefore names the group on a row where the sender is a member (`groups: [{id, name, member}]`, with a note saying it is their own text), and it resolves that name **at read time** from your own records rather than writing it into the stored message, so history is never rewritten when a member joins later and a person in two groups gets both names instead of a silently picked one.

`heyphony group show dinner` then prints the thread: your sends and their replies in one order. because the carrier contributes nothing, an inbound row is a member's text matched by membership, and the output says exactly that rather than implying a group message arrived.

`heyphony group reply dinner --text "seven then" --replying +1...` is what "reply to the group" can honestly mean here. it goes to every member through the same one-recipient rail, so the replier receives it in the same thread they used, as if you answered them, and every other member gets their own copy. nobody sees a group, and the command output carries that sentence rather than leaving it to be discovered.

### the code the group carries, so a reply can name itself

membership is a guess, so a group gets a code of its own at the moment it is created: four characters drawn from an alphabet with no B, I, O, S, 0, 1, 2, 5 or 8, because a code gets read aloud, copied off a screen and typed back, and those are the pairs that turn one into another. `heyphony group new` prints it and `group show` keeps printing it.

the code rides on the end of what members receive, eight characters and no more: `seven then` leaves as `seven then\n\nref K7QD`. that is the whole point of it. a member's reply can then **name** its group instead of being guessed at, and a member can answer with the code alone if they want to be unambiguous. `--no-tag` sends the body by itself, and the output says the cost rather than leaving it to be discovered: eight characters can push a body near the ceiling into a second segment, which is a second message and a second charge.

so attribution is a ladder with the evidence named, not a single rule. a body quoting the group's code is `by: "code"` and certain. a text arriving on a did the group holds is `by: "number"` and certain. no code, one group in our records is `by: "membership"`, reported as a guess, and no code with two candidate groups is `by: "ambiguous"`, which reports both and picks neither. every inbound row carries `certain` beside the name, because "this is bo's group" and "this came from a number that is in bo's group" are different claims and the second one is the one that could be wrong.

the strongest form is a number of its own: `group new --number +1...` attaches a did to the group, and then a reply is *addressed* rather than inferred, which also covers a member texting from a phone we never recorded. it costs a number per group, which is why it is optional rather than the default, and it still starts no carrier group thread, so the members still do not see each other.

and the code is not a secret, which is stated in the command output as well as here: it names a conversation, not a person. anybody holding the message can quote it, so it never proves who is writing, only which group they mean. it also cannot recover a reply whose tag was deleted, a text somebody forwarded from the message, or a carrier group mms, which arrives with its members in a payload this package does not parse.

two limits, stated because they are invisible otherwise. a real carrier group mms from somebody else arrives as an mms from the group or the original sender with the members in a payload this package does not parse, so it is not turned into a group and no media is read. and membership is the only marker there is, so a member texting you one-to-one about dinner is indistinguishable from their group reply, which is a property of the rail and not of the code.

and the thing people assume wrong, so it is in the command output as well as here: most carriers do not carry a group sms as a group. each member receives a one-to-one text from your did, with no sign that anyone else exists. the shared transcript is in your records, not in their phones, and no carrier group thread is started.

### looking a number up is a read, and that is why it is the safe half

`heyphony --lookup +447700900123` answers what a number is from the plan that issues it: `mobile` for a range issued for mobile services, `landline` for a geographic one, `voip` for the uk's own 056 range, `personal numbering` for 070. it also answers the question behind the question, `receive_text`: a mobile range can take a text, a geographic landline mostly cannot.

`heyphony --lookup +1555... support` answers per service instead, and this is where the tool refuses to be clever. a numbering plan can say whether a range can receive a code at all. it cannot say whether this particular number already has a whatsapp account, because that is a fact held by whatsapp and nobody else. so the verdicts are `possible`, `unlikely` and `unknown`, never a boolean, and `heyphony --lookup +1555... probes` prints the exact probe each service would need along with what running it would do: one of them sends an sms to that handset, and two of them lean on undocumented endpoints.

`+1` is where the two kinds of evidence separate cleanly. the north american plan encodes no **line type**, so a +1 number comes back `type: unknown` with `carrier-question` as its evidence and the carrier-lookup adapter named and marked unwired. it encodes a great deal of **geography**: the area code is assigned to a country, a territory or a region, so `heyphony --lookup +13405551234` answers `VI`, `U.S. Virgin Islands` and, for a geographic code, a place like `New York, NY` or `Ontario`. `+1` is not the united states and canada: the plan is shared by 25 countries and territories, from puerto rico and the us virgin islands to jamaica, bermuda and trinidad, and the area code also says whether the number is geographic, non-geographic, toll-free, premium or a personal follow-me number.

the same reader takes the other two address forms a person actually has. `--lookup dana@icloud.com` reads an address: the local part says whether it is a person or a shared desk, the domain says who issues it, and the answer is `possible`, `unknown` or `unlikely` for iMessage rather than a guess. Apple issues an iCloud account one of three address forms, so `@icloud.com`, `@me.com` and `@mac.com` are apple account addresses by construction, which is the strongest thing an address can say about iMessage. each answer also carries a three valued `matrix`: `imessage: true` for an address, because iMessage routes to an apple account and an address can be one, `signal: true` for a signal handle, and `null` where the capability belongs to an account rather than a string. capability is a boolean, existence keeps its verdict. every answer also carries a `fallback` ladder, so a line showing `imessage: unknown` says what comes next: `rcs` (the carrier's universal profile, which follows the text evidence) then `sms`, and a ladder that reaches nothing says so instead of leaving the caller to try another app.

`--lookup alice.42` reads a username, which is the one form this package deliberately cannot route and therefore has to be honest about: signal wants a nickname and a discriminator, whatsapp wants a plain handle, and `alice.42` is legal on both while naming a different account on each.

for one person there is a better instrument than a scanner, and it is resolution: signal's own client library can turn a username or a `signal.me` link into an account id without sending anything, and a small resolver on top of libsignal (`signal-whois`) does exactly that from an identity you already own. that is one request, one exact string, and the thing it returns is a pseudonym, so the output names all three limits. whatsapp has no such path, which the output says rather than dressing a first message up as a check.

turnkey osint tools do answer the questions this reader withholds (holehe for accounts behind an address, sherlock and maigret for usernames across hundreds or thousands of sites, phoneinfoga for numbers). they are named on the lookup page with what each answers and what it costs, and kept outside this package for three reasons: the cost lands on the person being looked up, the site modules rot, and a scan across thousands of hosts is not a lookup.

when the plan cannot fill a field, the answer says so with the reason rather than leaving a null: a toll-free code has no region because a toll-free code is national by design, and that empty region is the plan being exact.

a whole number is not always needed either. the geography sits in the first three digits, so `heyphony --lookup +1212` answers from the area code alone and says the subscriber digits were not needed, which is this half's version of preferring a domain to a local part.

`heyphony lookup eval` runs a labelled fixture corpus and counts a claim beyond the evidence as overreach, separately from a wrong answer: 20 cases, 20 passing, 0 overreach. the fixtures and the tables share an author, so a pass proves the code agrees with the table and not that the table is right, which is the same contract as themailtell and the reason the numbers are printed with that sentence attached.

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
cd npm && npm pack && npm i -g ./heyphony-0.3.0.tgz
npx heyphony status          # or npm i -g heyphony, both straight from the registry
```

the url install needs neither node nor git, which is why it is first. the package is on the npm registry as `heyphony@0.3.0`, published on 2026-11-03, so `npm i -g heyphony` and `npx heyphony` are live routes rather than promises. [npm/publish.md](npm/publish.md) is the runbook that got it there, including what the next version has to do.

an agent installing this should read [npm/agents.md](npm/agents.md) instead of this page, because it says which four commands to run, which two questions are for its human, and what it is not allowed to attempt.

## three places it can live

the command is the same everywhere; what changes is which computer holds the registration, the secret and the catcher, and what happens to all three when that computer sleeps. there are three honest answers, and the setup guide in this repo is about the instructions for each: an agent on a local computer, where the answer depends on which computer, a computer of its own in a container or a cloud vm, and a spawnable guest from the spawnables line.

## the licence, and why it is not mit

this is a source available licence, not an open source one: bsl shaped, with the permitted purposes of the functional source licence and the three hard prohibitions of the elastic licence. you can read it, run it, modify it, and ship your own agent on it, including in production. what you cannot do is take it and sell it as the thing it replaces, or strip the notices out of it.

each version converts to mit two years after it is released, and the table in [LICENSE](LICENSE) dates every version that exists. versions that are not listed have not been released.

## what it will not do

there is one claim this page could make that would sell better, and it is the one it is not making: that a number from here gets your agent through a verification code. it does not, reliably, and the reason has nothing to do with the quality of the setup.

### the 2fa claim, which we are not making

almost every product that hands an agent a number does the same thing this repo does: it gives you voip over sip. that number is auto blocked by a growing list of banks and social media services, and there is no path around it, because what is being detected is the number type itself.

the refusal is not a verdict on this package. it is adversarial detection aimed at sybil campaigns, which register voip numbers by the thousand, and the platforms answered that with outright prohibition rather than a risk score. the disparate impact lands on every legitimate sip number in existence, and it lands on yours here. so the page says what is true instead of what converts, and claims two things:

- **we do not promise a 2fa path.** where a service accepts the number, that service has not closed the door yet, and nothing in this repo is defeating a check. if a workflow needs codes, it needs a handset, and it should not be built on this.
- **we do not hold numbers in a pool.** there is no shared inventory here whose reputation could be tainted by somebody else's traffic. the number is bought in your name from a provider you chose, so its history is only the history it was given.

### what outbound is, and what it is not

`sms on this number, one message at a time.` the rail sends when the gate is open (`HEYPHONY_SEND=allowed`) and the call says so (`--send`), records the message in the same thread as what came in, and refuses a list, a loop and a schedule, because a campaign is a different product with consent, attested origination and a registered business behind it.

the lookup reads a plan and never dials. that is the same split as the rest of the package at a different scale: reading is patient and cheap, and everything that touches somebody else's phone has a gate, a ceiling and a stated consequence.

three shapes ride that one rail: a single reply, a voicemail, and a small named group. all three are the same act at different volumes, which is why none of them has a queue, a retry, a schedule or a quiet-hours engine. one of them is a call, so `HEYPHONY_CALL=allowed` is its own gate rather than a second meaning for the text gate.

provider terms, quiet hours, and what the recipient actually agreed to are yours. a tool that respects a gate cannot also audit a business, and pretending otherwise would be the dishonest version of a safety feature.

### and nothing here publishes

no stream, no account to create, no audience to grow: a number that can be reached.

### the rest is in the argument

those are not gaps waiting for a sprint. they are the limit of what a number of this type can do, and [theidea/](theidea/) is where each one is argued rather than listed.
