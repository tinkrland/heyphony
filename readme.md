# meetings

*the live half: joining the room where the humans are, speaking in it, and showing a screen when that is the point*

a phone number reaches a person who picked up. a meeting is the other shape of the same need: a room, a link, a time, and somebody expecting a participant. this branch is about arriving in that room as a participant an agent can drive, rather than as a transcript nobody can interrupt.

it used to be called `omnimeetings`, which promised a whole platform. the name is `meetings` here because the branch is about the join, and everything around it (a calendar, a memory, a recap) belongs wherever those things already live.

## the three platforms, and what each one actually is

the table is generated from `rails.py`, and a test fails when the page and the data disagree.

| rail | how a bot joins | the signature | audio | state |
| --- | --- | --- | --- | --- |
| `zoom` | meeting sdk join token, or the browser client with a link | hs256 jwt over header and payload, iat backdated 30 seconds for clock drift, exp two hours | livekit room | contract |
| `googlemeet` | a browser participant, because there is no bot api | none, the invite is the permission | livekit room | contract |
| `teams` | a browser participant, tenant policy permitting | none, and a tenant can refuse outside guests | livekit room | contract |

**state is `contract` on every row.** nothing on this branch joins a meeting yet. the shape, the signature and the refusals are written down; the participant is not, and a page that implied otherwise would be a page about software that does not exist.

## the signature is the only part worth being exact about

zoom is the one platform with a documented programmatic join, so it is the one where a wrong field is a silent failure. the join token is a jose compact structure built from the sdk key and secret: an hs256 header, a payload carrying the meeting number, the role, and the two timestamps, a signature over those two base64 parts, and a token assembled from the signature, the message and a short random suffix. the iat is backdated because a clock half a minute fast is a token that is not yet valid, which presents as a confusing 401 rather than a clock problem.

google meet and teams have no equivalent. a bot joins those as a browser participant with the invite in hand, which means the honest description is "a headless browser wearing a normal participant's clothes", not "an api".

## the audio is a room, not a telephone call

inside a meeting the agent is a participant in a livekit room: it subscribes to the mixed audio, and it publishes its own track. that is a different media path from the sip call on `main`, where the client owns one stream and the number owns the identity. the two do not merge, and pretending they do would mean writing a bridge that pumps two clocks and two codecs, which is a project rather than a helper.

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
