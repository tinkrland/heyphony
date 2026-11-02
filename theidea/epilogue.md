# epilogue: back to the basics

*why the interesting version of agent telephony is an old one*

there is a strange moment in this project where you go looking for how to give an agent a phone number, read four landing pages about "ai native voice infrastructure", and then end up reading a manual for a private branch exchange written before the first iphone. that moment is the point of this page. the answer was not ahead of us. it was behind us, in an office closet, humming.

## the pbx nobody remembers

a pbx is a private branch exchange: the box in the basement of an office that owned the extension numbers, decided which handset rang, and handed calls out to the phone company through a trunk. dial 4 for reception, dial 212 for the person in accounts, and the whole company shares a handful of outside lines. every feature people now think of as modern, which is hold, transfer, voicemail, an auto attendant, a call queue, a menu that says press one for sales, was invented on that box in the eighties and nineties because a receptionist was expensive and a machine was patient.

then voip arrived, and the same machine got cheaper. asterisk in 1999, sip as a standard shortly after, and suddenly the pbx was software, the handsets were optional, and the trunk was a tcp connection rather than a pair of copper wires. the interesting consequence is the one everybody immediately forgot: after voip, the thing on the other end of a phone number does not have to be a phone. it can be a program. this is not new. it is twenty five years old. every ivr you have ever shouted at is a program answering a number.

so when the question is "how does an agent get a phone number", the answer was written down in 1999: buy a number from a carrier, point it at an endpoint you control, and answer it with whatever you like. the 1999 answer needs a modern wrapper, not a modern replacement.

## the softphone that never left

the other half of the inheritance is the softphone, which is a phone that is only software: linphone, zoiper, jitsi, ekiga, and a hundred others. it registers to a server with a username and a password, holds a tcp connection open, and turns a network stream into sound. that is the whole job. the reason it is worth naming is that a softphone is exactly what an agent needs and exactly what an agent is bad at: it needs the registration, it does not need the sound.

which is why this folder does not ship a phone. it ships the registration, the inbox, the log, the transcripts, and a socket a process can speak to. when a human wants to actually hear somebody, a softphone or a desk phone can register to the same number and it will ring there too, because a number is a rendezvous point rather than a device.

## what mcgyvering meant here

"mcgyver" is the right verb and it is not an insult. the shape of the work was: take a system that was built for humans with handsets, identify the exact four things a process needs from it, and bolt those on without pretending the rest does not exist.

the four things turned out to be:

**a number that reaches a process.** a did for about a dollar, and a registration on a host we already run, so the address is not the machine.

**texts that survive the machine being off.** because texts never travel over sip. they are provider events, so the provider holds them and posts them, and the agent reads a jsonl file later. this is the single most useful property in the whole lane and it comes free with the old infrastructure.

**voicemail as a file rather than a light.** the carrier already answers when nothing else does. the work is only to get what it recorded into a directory with a sidecar that says who called and what they said.

**a way to ask "what is new".** a mailbox has no read state, and a provider webhook has no opinion about whether anyone looked. so the read state is a sidecar, and it is ours.

that is a short list, and everything else was either already there or is a nice to have.

## what we tackled

in order of how load bearing it turned out:

- **the number, held properly.** the provider table, the registration, the generated config, and the rule that the credential lives on the host and never in a guest we intend to shred.
- **the catcher.** one url per provider, five payload shapes normalised into one envelope, an unknown shape stored rather than dropped, and a refusal to invent a field the provider did not send.
- **the inbox and the views.** numbered rows, stable handles, unread state, one body in full, calls from the client's own sqlite, voicemail files with honest "no transcript" instead of a guess.
- **the hooks.** what to paste where, which is different for every provider, printed as steps plus the exact api call for the ones that have one.
- **provisioning, up to the last step.** area stock and prices from an api, the order prepared rather than placed, and a paid step that stays a person's.
- **the launcher.** caught texts and voicemail in one thread with a person, because that is what a human would see in a phone app and an agent should not have to reconstruct.

## what we left alone

being a telco. running an sbc. buying numbers in bulk. a cdr pipeline. e911 address management, which is a legal statement rather than a field. becoming a call centre, which is where bulk outbound lives and where consent and attestation live with it. and inventing a protocol, because sip is fine and the only thing wrong with it was that it was written for a telephone rather than for a process with a json parser.

the honest summary of the whole experiment, which is also the epilogue: an agent can have a phone number of its own, today, for about a dollar, on the machine it already has, if you are willing to talk to the network that already exists instead of waiting for one that was designed for you.
