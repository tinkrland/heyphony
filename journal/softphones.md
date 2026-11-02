# softphones, from zero

*what a softphone actually is, one step at a time, without assuming you have ever configured one*

a softphone is a telephone that is only software. no handset, no copper, no box on a desk. it runs on a computer, holds a connection to a phone system, and turns network packets into sound and back. that is the whole definition, and everything confusing about the topic comes from the fact that the word "phone" hides about six separate jobs inside it.

this page walks those jobs in order. each step is one thing that has to happen for a call to work, and each one is a place where an agent's needs and a human's needs stop matching.

## step 0: what a number even is

before any of this, a phone number is not a device. it is an entry in somebody's routing table, and the thing that makes it "yours" is that the carrier sends its calls to an endpoint you control. that endpoint is where a softphone lives.

the practical consequence: **owning a number is a routing arrangement, not a piece of hardware.** you rent a did for about a dollar a month, and you point it at an address. whatever answers that address is your phone. it can be a desk phone, a laptop with linphone on it, or a python process that writes json.

## step 1: registration (the phone says hello)

the softphone starts, reads a config file, and sends a `REGISTER` message to the provider: here is my username, here is my password, send calls for this number to this ip and port, and this registration expires in a few minutes, so expect me to renew.

three things follow from this step, and they explain most of telephony's weirdness:

- **the registration expires.** it keeps happening in the background. if the machine sleeps, the registration lapses, and the carrier starts sending calls somewhere else or nowhere.
- **one number, one registration.** a second machine registering the same did does not give you two phones. it gives you a race where the carrier picks whichever registered last.
- **the password is long lived.** it is a secret that sits in a config file, which is why the file is written 0600 and why it belongs on a host rather than inside a machine you intend to shred.

## step 2: the invite arrives (signalling)

somebody dials the number. the carrier sends an `INVITE` to the registered address: caller id, the number dialled, and an offer of what media this call could be.

the softphone's job here is to answer, decline, forward, or ignore, and every one of those is a *message*, not a sound. a human experiences this as a ringing phone. a program experiences it as an event with a call id on it, which is the first place an agent has an advantage: a ringing phone demands attention immediately, an event in a socket does not.

## step 3: they agree on a format (codec negotiation)

a call is audio, audio is big, so it gets compressed. the offer in the invite lists codecs the caller supports, the answer lists the ones the callee supports, and they pick one both understand. `opus` is the modern default, `g711` (ulaw/alaw) is the ancient one that always works.

when two systems fail to connect despite both looking correctly configured, this is usually where: they agreed on a codec one of them cannot actually encode, or they agreed and then disagreed about the packetisation. it is a negotiation, not a setting.

## step 4: the media starts (rtp)

the audio does not travel over sip. it travels over `rtp`, a separate stream on a separate port, and this separation is the single most useful fact in the whole subject:

- sip is a control channel. small messages, easy to proxy, easy to log, easy to fake.
- rtp is the payload. big continuous streams, sensitive to latency, and it must reach the endpoint directly or through a relay that understands it.

this is also why **texts have nothing to do with any of the above.** an sms is not a media stream. it is an event the carrier holds, and it arrives by webhook or by email, which is why a number can receive a text while the softphone is switched off entirely.

## step 5: the call ends, and something writes it down

hang up produces a `BYE`, and the carrier's accounting system writes a call detail record: who called whom, when, how long, and whether it was answered. softphones keep their own local copy, usually in a small sqlite database, which is where `heyphony calls` reads from.

a human never looks at a cdr. an agent reads nothing else, because a cdr is the call log it can actually answer questions from.

## step 6: where the pbx was standing

everything above is two endpoints talking. in an office there was a machine in the middle, and it did the jobs a single softphone cannot:

- it owned the **extensions** (the short numbers inside the building) and decided how they mapped to the outside world
- it held the **trunk**: one connection to the carrier carrying many outside lines, so forty people shared eight lines
- it **routed**: dial 9 for an outside line, dial 4 for reception, ring this group when that number is called
- it provided **features**: hold, transfer, voicemail, auto attendant, call queues, music on hold
- it **recorded** what happened, for billing and for "who called while i was out"

in 1998 that was a box. after asterisk it was software, and after sip became normal the box and the software were mostly the same thing. the point worth keeping: **a pbx is the thing that makes a number answerable by an organisation.** the softphone is the thing a person holds.

## step 7: what we actually kept from all of it

a number, a registration, a config file in the format a client reads, an event stream instead of a ringing bell, and a log. what we did not need: a handset, a microphone, a screen, a human at the keyboard at the moment the call arrives, or a pbx, because there is one person to route to and no queue to build.

that subtraction is the whole adaptation, and [the table next door](pbx-vs-softphone.md) is the same story in rows.
