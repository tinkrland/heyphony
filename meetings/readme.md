# meetings

*the room, joined as a participant, with a signature for the one platform that gives you one*

this folder is the lane. the data is `rails.py` one level up, because the branch page, the signature notes and this file all read from the same place, and a table in two files is a table that drifts.

## the three ways in

**zoom** is the only platform with a documented programmatic join, so it is the only one where this branch mints anything. a join token is a compact structure: a base64 header carrying `HS256`, a base64 payload carrying the sdk key, the meeting number, the role, the issued time and the expiry, an hmac-sha256 signature over those two parts, and a random tail so two joins of the same meeting never look alike. the issued time is backdated thirty seconds, because a clock half a minute fast produces a token that is not yet valid, which presents as a 401 rather than as a clock problem.

what the signature covers is worth being exact about, because a token that verifies when it should not is worse than one that fails. the signature covers the header and the payload. the tail is a nonce, not a claim, so changing it changes nothing and the token still verifies. changing either covered part ends the token, and `verify_zoom_token` recomputes over exactly what the carrier recomputes over.

**`googlemeet`** has no token and no bot api. the join is a browser participant with the invite in hand, and the honest description is a browser wearing a participant's clothes rather than a client speaking a protocol. the gate is a browser profile that is already signed in, and there is nothing to sign.

**teams** is the same browser join with one more refusal in it: a tenant can decide that outside guests do not join, which is the platform being correct rather than the participant being broken. its gate names a tenant id so the plan can say which question is open.

## the microphone, cheapest first

a browser we launch needs no audio device at all. chromium answers `getUserMedia` from a file given `--use-fake-device-for-media-stream` and `--use-file-for-fake-audio-capture=<wav>`, which is the whole rail for a browser room and installs nothing.

a native client (the zoom app, linphone, baresip) needs a real source instead: a pipewire null sink and a remap source, two `pactl` calls, after which the client's microphone list shows a device named whatever we chose. pipewire is mit and pulseaudio is lgpl-2.1, and the same two calls work on both.

macos and windows need an installed device because neither ships one. blackhole is the free software answer on macos; the usual windows virtual cable is donationware and closed source, and it is named that way in `audio.py` rather than described as free.

obs is not the microphone. it is free software and it stays in the stack for scenes and the virtual camera, but its virtual audio device is a macos extra, so on a linux host obs was never the rail and nothing here needs it for one. `bin/meetings audio --audit` answers the whole question as data.

## speaking inside the room

the agent is a participant in the room's own livekit room: it subscribes to the mixed audio and publishes its own track under the identity the room already knows. no new person is requested into the call, because the agent is not a new person, it is a mouth on the connection it already holds. the gate is three livekit variables, and `readiness` reports which of them are set rather than assuming the rail is open.

## the screen

`getDisplayMedia` from inside the browser that joined. the browser shares its own screen and nothing is re-streamed through this branch. which surface is shared is the human's click, and a browser that auto-selects the screen is a browser configured to, not a branch that grabbed one.

## what it refuses

### no cold join

a link is not an invitation, and a meeting number is guessable enough that treating it as one is how a bot ends up in a stranger's standup. the invite, and the person who sent it, are the permission.

### no recording, and nothing published

joining and recording are different consents, and the moment a recording exists it is a file with other people's voices in it that outlives the meeting. nothing in this folder opens a recorder, and a recording that needs publishing is somebody else's decision made somewhere else.

## the state, and what would change it

every platform here is `designed`: the join path is read from the platform's own documentation, the token is minted and re-verified, and the plan names the gate. no meeting has been joined from this branch, so nothing is `verified`, and the word `verified` is reserved for a real room with the human who invited the agent saying it worked.

## the copy on the other line, named

`omni` carries the same lane as a registry row, because a branch cannot import another branch and that line has to list nine of them. its version is the shallow one: carrier, gate, state, and the plan. the token, the microphone rail and the shim are here, and this is the page with the round trip in it. when the two ever disagree, this one is the one held by tests.

this branch also does not sign anybody up. an account elsewhere needs four legs (an address, an inbox, a browser, sometimes a phone), and that errand is `omni`'s `signup` verb. joining a room and acquiring the identity that accepts an invite are different jobs.
