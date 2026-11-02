# what a softphone was for, and what we bent it into

*the same object, two jobs: one built for a person in an office, one bent into an endpoint for a process*

read [softphones, from zero](softphones.md) first if the words registration, invite and rtp are still abstract. this page assumes the mechanism and compares the intent.

a softphone was never designed for an agent. it was designed to replace a plastic desk phone with an app on a laptop, and every design decision in it follows from that: it assumes a person is looking at it, that the person wants to hear something, that the person will answer within a few rings, and that the person is one extension inside a company that has a phone system in the basement.

the agent has none of those properties. it is not looking, it does not hear, it may be asleep, and it is not an extension of anything. so the work was not to build a new protocol, it was to take the client, keep the parts that describe *where calls go*, and drop the parts that describe *a human experiencing them*.

| | what a softphone was made to do, next to a pbx | what heyphony adapted it to |
| --- | --- | --- |
| who is on the other end | a person at a desk, in an office, during office hours | a process, on a host, at any hour, mostly not looking |
| what the number is for | being one extension in a company's numbering plan | being the agent's own address, reachable from anybody's phone |
| the registration | a client keeping a line alive so a colleague can reach you | the same thing, plus the rule that it lives on the host so the address outlives any guest |
| the invite | a bell that has to be answered, socially, in real time | an event on a json socket that can be answered, ignored, or answered tomorrow |
| the media | audio for a human ear, so codec support must be complete | a stream that matters only when it is being turned into text; text-first means most traffic never becomes media at all |
| the interface | a window with a dial pad, a hold button and a contacts list | `ctrl_tcp`, json in and json out, and a cli that emits the same objects |
| the audio devices | speaker, microphone, ringtone, hold music | none required; recording and transcription attach to the stream, not to a sound card |
| presence | green dot, "in a meeting", do not disturb | nothing. an agent does not owe anyone a status, and pretending to have one is theatre |
| hold, transfer, conferencing | features a pbx sold, because offices needed them | refused by omission: one agent, one conversation, and a transfer is a person's decision |
| voicemail | a blinking light and a playback menu on the handset | a file plus a sidecar with sender, seconds and transcript, readable without ears |
| call history | a list you scroll when you wonder who called | the cdr, read as data, because it is the only honest account of what happened |
| the pbx itself | the box that owned extensions, routed calls and recorded them | not built at all: there is one endpoint and no queue, so the provider is the routing table |
| the config file | something a human typed into a settings dialog | generated from the client's own schema, written 0600, and tested against that schema so it cannot drift |
| what "answering" costs | attention, immediately, for as long as the call lasts | a write to a jsonl file, and the option to answer when it suits |
| the failure that hurts | the phone does not ring and you miss a client | the number is registered somewhere else, or nothing was awake to catch it, so the inbox is the only proof that matters |
| texting | not the softphone's job at all; sms lived elsewhere | the primary channel, because it is a provider event that waits politely, not a stream that needs you present |

## the three lines that changed the most

**attention became storage.** the whole point of a phone is that it interrupts you. the whole point of the adaptation is that it does not have to: a text is a row, a voicemail is a file, and an invite is a message with a call id. an agent that can defer is more useful than one that rings.

**the pbx disappeared into the provider.** an office needed a machine in the basement because it had forty people and eight outside lines to share, plus a receptionist's job to automate. one agent with one number needs none of that: the carrier already routes, the carrier already has voicemail for the providers that offer it, and "press one for sales" is a product decision nobody here is making.

**the human-shaped surface became a schema.** everything a softphone asked a person to click is a key in a dict here: provider, did, username, password, and the answers to the setup menu are the same answers as the flags. that is why a model can hold a phone number without touching a gui, and why nothing in this folder needs a screenshot to be operated.
