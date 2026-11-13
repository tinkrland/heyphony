# calling

*text first is not voice never*

this lane is inbound first and text first, but a phone number that cannot take a call is a pager. calling is supported, and it is supported in layers, because the honest situation is that a call is a media stream and a media stream is the expensive part.

## what a call actually needs

four things, each of which can fail on its own. a registration so the provider knows where to send the invite. an invite answered, which is signalling. a media path, which is rtp, and which needs the network between you and the other end to cooperate, with nat traversal and a codec both sides accept. and something to do with the audio once it arrives, which for a human is a speaker and for an agent is a stream that has to be turned into text and back.

the first two are solved by the sip client on the host, and they are what `heyphony connect sip` configures. the last two are where the choices are.

## the rails a call can ride

- **baresip on the host** is the client this folder decided on, and it is the rail for an ordinary call: it registers, it rings, it answers, it hangs up, and its `ctrl_tcp` module gives a process a json socket to drive it. recording and transcription attach to it by taking the audio the call is already carrying rather than by re-implementing the call.

- **livekit** is the rail for a call that is really a room: two-way audio with room semantics, participants, tracks, and the same stack the meetings lane uses. it is apache-2.0, it runs where you point it, and it is the right answer when the agent is joining something rather than answering a phone. publish the tts track as a participant and the "agent is on the call" problem becomes a participant problem, which livekit already solves.

- **call-e** ([heycall-e.com](https://heycall-e.com)) is the rail we would reach for when the call should be a *conversation* rather than a stream: a hosted voice agent that handles the conversational loop. it is the one rail here that asks you to hand a third party the audio and the reasoning, so the trade is made explicitly rather than by convenience: the client is built and audited against their published spec, and it refuses to run without `HEYPHONY_CALL=allowed` and a key of your own. `bin/callheavy dial --via calle` is the command. what is not proven is a live call to them, since no key has been spent.

## what exists today, and what does not

what is built: registration and config generation, the host client decision with its reasoning, the call log read out of the client's own sqlite, missed call filtering, voicemail as a file with an honest "no transcript" when none exists, `ctrl_tcp` driven from a process (`dial`, `answer`, `hangup`, and the four facts reported separately), the agent's ears and mouth on a live call through pulseaudio null sinks, and the hosted call-e client behind its gate. what is not built: a call over a real carrier registration, joining the call to a livekit room, and turning the audio into a transcript. what proves the middle of that list is two real baresip instances on one machine carrying a tone in each direction, which is a media path and not a telephone network; the readme says the same thing in one line, because a lane that overstates its call support is a lane nobody can debug.

## why text first anyway

because receiving is cheap and calling is not, in every sense. a text is a small provider event that waits politely until somebody reads it. a call is a real time commitment for both parties, it needs media to work, and it needs somebody present. an agent that gets a text can answer in a minute or an hour; an agent that misses a call has missed it.

that ordering is a design decision rather than a limitation, and it is the reason the number, the inbox, the catcher and the voicemail come before any of this page: they are the parts that work while nothing is awake, which is most of the time.
