# meetings

*the live half: joining the room where the humans are, speaking in it, and showing a screen when that is the point*

a phone number reaches a person who picked up. a meeting is the other shape of the same need: a room, a link, a time, and somebody expecting a participant. this branch is about arriving in that room as a participant an agent can drive, rather than as a transcript nobody can interrupt.

it used to be called `omnimeetings`, which promised a whole platform. the name is `meetings` here because the branch is about the join, and everything around it (a calendar, a memory, a recap) belongs wherever those things already live.

## the three platforms, and what each one actually is

the table is generated from `rails.py`, and a test fails when the page and the data disagree.

| rail | how a bot joins | the signature | audio | state |
| --- | --- | --- | --- | --- |
| `zoom` | meeting sdk join token, or the browser client with a link | hs256 jwt over header and payload, iat backdated 30 seconds for clock drift, exp two hours | livekit room | designed |
| `googlemeet` | a browser participant, because there is no bot api | none, the invite is the permission | livekit room | designed |
| `teams` | a browser participant, tenant policy permitting | none, and a tenant can refuse outside guests | livekit room | designed |

**state is `designed` on every row.** the join path is implemented rather than merely described: the zoom token is minted and re-verified, the plan for a given platform is built and names its gate, and the microphone rail answers per room. nothing on this branch joins a meeting yet, so nothing here is `verified`, and that word stays reserved for a room with the person who sent the invite saying it worked.

## what actually runs here

`bin/meetings` is the one command, and it is a shim over `python3 -m meetings.cli` so the module is the thing you can read. `join --platform --meeting` answers what that room takes: the join path, the signal the platform allows, the audio rail, the gate, and which of those gates are missing today. `--platform zoom` with its two variables set also returns the minted token, because a token is the answer to "what do I paste into the sdk", not a separate errand. `audio` answers the microphone question per room, with `--audit` for the free software half, and `sign` is there for the case where the token is all anything wanted. `status` reports every platform and what each is missing, and `--setup` returns the whole lane in the shape the other lanes use.

the modules are three. `rails.py` is the data: the three platforms, the jose fields, the refusals, the state with its evidence. `meetings/meetings_lane.py` is the code that acts on it: the token, the verification, and the join plan, with `PLATFORMS` derived from `rails.py` rather than written again beside it. `audio.py` is the microphone story, kept as data plus three small functions so the audit is a lookup rather than a mood.

## the signature is the only part worth being exact about

zoom is the one platform with a documented programmatic join, so it is the one where a wrong field is a silent failure. the join token is a jose compact structure built from the sdk key and secret: an hs256 header, a payload carrying the meeting number, the role, and the two timestamps, a signature over those two base64 parts, and a token assembled from the signature, the message and a short random suffix. the iat is backdated because a clock half a minute fast is a token that is not yet valid, which presents as a confusing 401 rather than a clock problem.

google meet and teams have no equivalent. a bot joins those as a browser participant with the invite in hand, which means the honest description is "a headless browser wearing a normal participant's clothes", not "an api".

## the audio is a room, not a telephone call

inside a meeting the agent is a participant in a livekit room: it subscribes to the mixed audio, and it publishes its own track. that is a different media path from the sip call on `main`, where the client owns one stream and the number owns the identity. the two do not merge, and pretending they do would mean writing a bridge that pumps two clocks and two codecs, which is a project rather than a helper.

getting a microphone at all is the part people get wrong, because a virtual microphone is not one thing. a browser room needs no device: chromium answers getUserMedia from a wav with two flags, which is the whole rail for zoom web, meet and teams. a native client needs a pipewire null sink and a remap source, two pactl calls, both free software. obs is free software and still not the microphone, since its virtual audio device is a macos extra. macos and windows need a device installed, and the windows one is closed source, which `audio.py` says out loud instead of describing it as free.

## what a human still does

**sends the invite.** there is no directory to scrape and no cold join. a meeting an agent was not invited to is somebody else's room.

**stays in the loop on recording.** joining and recording are different consents. this branch is about the first one, and every page that mentions the second says the human presses the button.

**decides what the agent is for in the room.** taking notes and speaking are different products with different failure modes: a silent notetaker that mislabels a speaker is annoying, and an agent that talks over people is worse.

## what it refuses

### no cold joins

a link is not an invitation, and a meeting id is guessable enough that treating it as one is how a bot ends up in a stranger's standup. the invite, and the human who sent it, are the permission.

### no recording by default

the moment a recording exists it is a file with other people's voices in it, and it outlives the meeting. capture is a decision for the person who called the meeting, and nothing here turns it on quietly.

### no broadcast

joining a room is not going live to an audience. a stream is a different rail with a different consent problem, and it is not on this branch.
