# forwarding

*sending a call or a message somewhere other than the endpoint that owns the number, and being honest about which of those two things is even possible*

this is an exploration branch, not a feature. nothing here calls a carrier, nothing writes a rule to a provider, and every capability in `src/forwarding.py` is marked `verified: False` because nobody has set one against a real number yet. the point of the branch is to answer the two questions properly before any code pretends to.

the two questions look symmetrical and are not. a call can be handed off at five different moments, and every one of them is a standard feature a pbx has had since the 1980s. a text has no such ladder: either the carrier re-addresses it before it ever reaches us, or we receive it and send a second one, which is a re-send wearing forwarding's clothes. one of those survives the host being asleep and the other does not, and that difference is the whole design.

## a call can be handed off at five moments

| mode | when it fires | where it is set | survives the host being down |
| --- | --- | --- | --- |
| `unconditional` | every call, before the endpoint rings | carrier, or the endpoint as a 302 | yes |
| `busy` | when the endpoint answers 486 busy | carrier, or the endpoint | no |
| `no_answer` | after the carrier's ring timer, usually 15 to 30 seconds | carrier, or the endpoint | no |
| `not_reachable` | when the endpoint is unregistered or the host is asleep | carrier | yes |
| `selective` | when the caller matches a rule: exact number, prefix, or list | a handler we write, or a carrier that sells caller based routing | no |

### unconditional is a redirect, and that is a different product

forward always means the number stops being yours to answer. an agent behind it receives nothing, and cannot decide anything per caller, because the decision was made by configuration before the call arrived. that is fine when the intent is "this number is a front door and the room is elsewhere", and wrong when the intent is "the agent should still get the interesting calls", which is what people usually mean.

### busy and no_answer both need a host that is awake to be any of those things

busy requires a registered endpoint that can genuinely answer 486. a sleeping host is not busy, it is unreachable, and the two get confused constantly: a number configured for forward-on-busy simply rings out when the machine is off, and the person who set it believes they configured a fallback. no_answer is the same trap with a timer on it, and the timer is the feature. set it shorter than the time the agent actually takes to pick up and every call is forwarded, which looks like forwarding being broken and is actually forwarding working exactly as configured.

### not_reachable is the mode that matches a number on a host that sleeps

this is the one worth having here. a number on a machine that is off most of the day is unreachable most of the day, so the carrier's unreachable forward is not an edge case, it is the normal path. it is also narrower than it sounds: it fires when registration has already dropped, not when the host is up and wedged with the client still registered. a host that is awake and broken is a supervision problem, and no forwarding mode will catch it.

### selective is the one where the carrier will not save us

forwarding on particular numbers is the interesting idea and the least portable. it is not a sip primitive. where a carrier offers it, it is a dashboard feature, and where a carrier does not, the only honest implementation is a branch in a handler we write: the call arrives, we read the caller, and we either answer it or hand it off. that costs a second leg, needs the host awake to make the decision, and it is still the right place to do it, because the alternative is assuming a routing feature exists on a provider that has never documented one.

## a text cannot be forwarded, only relayed

| mode | what actually happens | where | survives the host being down |
| --- | --- | --- | --- |
| `carrier_relay` | the carrier sends the inbound text to an email or an xmpp jid | carrier | yes |
| `webhook_relay` | the carrier posts it to our catcher, we send a second text | our host | no |
| `email_fallback` | it arrives as mail because the carrier does that for a number you already have | carrier | yes |
| `store_and_relay` | we hold it and deliver when the host wakes | our host | yes, late by however long it slept |

### the carrier relaying it is the only version that is really forwarding

when the carrier re-addresses a text to an email or a jid, the message exists somewhere even if this machine never wakes. the cost is the thread: whoever reads the relayed copy is reading mail, and replying from it reaches nobody unless the carrier accepts replies back into the number. that is a real product decision, not a bug, and it is the same decision this repo already made for inbound texts on the providers whose text style is email.

### relaying it ourselves is a re-send, and the naming matters

the webhook shape is the one that tempts you into calling it forwarding. it is not: the recipient sees a message from **this** number, the original sender sees silence, and the two hops are two messages with two costs and two delivery reports. that is a legitimate feature (a triage inbox that pushes to a phone), and it is a different feature than the one the word implies. it also needs the host awake, so it cannot be the answer to "who gets this while the machine is off".

### store and relay is fine for a digest and wrong for an answer

holding a text until the host wakes is trivial and it is the wrong shape when the sender expected a reply in a minute. late is a delivery property nobody asked for, so it belongs behind a decision, not on by default.

## what a given provider can actually be asked for

the classification below is derived from each provider's own forwarding sentence and inbound text documentation, both already on `main` in `src/providers.py`, rather than from anything this branch invented.

| provider | call forwarding | message relaying | survives the host being down |
| --- | --- | --- | --- |
| `voip.ms` | carrier conditional | carrier relay, to email | texts and voicemail |
| `flowroute` | not claimed | webhook to our catcher | texts only, because our catcher stores them |
| `anveo` | dashboard call flow | url forward with placeholders | texts only |
| `signalwire` | a handler decides | webhook to our catcher | nothing |
| `questblue` | did pointed at a trunk | both: post to a url, or relay to email, xmpp, 3cx or yeastar | nothing claimed |
| `bulkvs` | forward or failover on the number record | webhook to our catcher | nothing claimed |
| `jmp.chat` | the jabber account is the address | nothing to relay, the jid is the address | texts |
| `voyced` | standard did routing | no inbound texts | voicemail |
| `voxacall` | trunk routing | no inbound texts | nothing claimed |
| `bitcall` | outbound trunk only | no inbound texts | nothing claimed |

two of those matter for this branch. `voip.ms` is the one where a conditional forward and a text relay are both things the carrier does without us, which makes it the natural first provider to try a real forward against. `signalwire` is the one where selective forwarding is genuinely ours to implement, because its model already expects a handler to decide.

## matching a particular number

a rule is a match, an action and optionally a window. the match kinds are `any`, `exact`, `prefix` and `list`, and they are deliberately few: an exact match wants a full e164 or it will never fire, a prefix is what "all the UK mobiles" actually is, and a list is the one that grows into a spreadsheet nobody maintains.

three things get checked before a rule is stored, and all three are cheap to check and expensive to discover later. a rule that matches nothing, because the value is not an e164 or the list is empty, is not a rule. a rule that points at a premium rate number is the international revenue share fraud pattern, where the person paying for the forwarded minutes is whoever owns the number being forwarded. and a rule that forwards back into a number that forwards forward again is a loop, which rings legs until somebody notices the bill.

### the loop is checked before the configuration, not after

`chain_problem` walks the forward map and reports the cycle rather than the first hop, because "A to B" is not obviously wrong and "A to B to A" is. this is the one piece of this branch that could ship as code tomorrow and be useful with no carrier integration at all: a validator that refuses to store a forward set containing a cycle.

## what it refuses

### a forward that is a campaign

pointing a number at a list is bulk outbound with an extra step, and this repo already refuses the campaign. the forward does not get a pass for being configuration.

### a premium or revenue share target

the fraud pattern above, named so nobody configures it by accident and finds out from a carrier's abuse desk.

### somebody else's number

you can forward what you hold. a target you do not own is a reroute of traffic that is not yours to reroute.

### a forward that hides itself

a caller who reached a different endpoint than the number they dialled should learn that from the greeting, not from a surprise. that is a presentation decision made for the callee, and it is not one this branch makes on their behalf.

## the state, and what would move it

every mode here is a shape with a documented trigger, a place it can be set, and a named catch. none is wired, so none is `verified`, and the word stays reserved for a real forward on a real number with somebody on the other end confirming what they heard. the shortest honest path to the first verified row is a `voip.ms` number forwarding on no answer to a second did, because both ends are things the carrier already does and neither needs code from here.
