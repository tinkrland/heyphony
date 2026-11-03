# meetings

a meeting is a channel that is a room, not an inbox. this folder holds the joining
and the two rails that make a room usable to an agent: audio through livekit, and a
shared screen from inside the spawnable that joined.

platforms, each with its own way in:

- **zoom**: the web sdk in the spawnable's browser, with a join signature minted by
  the backend (hmac-sha256 over `base64(header).base64(payload)`, wrapped in a token
  with a random tail so two joins never look alike). ported from clawtel, round-trip
  tested here.
- **google meet**: the room's own web client in the browser. no token, no official
  join api, so the honest state is "a browser joins, and it is a browser".
- **teams**: web client plus a tenant permission for the app. the gate is a tenant id,
  and a private tenant will refuse a stranger's app, which is correct.

the two rails:

- **audio (livekit)**: the agent joins the meeting's own livekit room as a participant
  under the identity the room already knows, publishes tts, subscribes for stt. no
  new person ever requests into the call, because the agent is not a new person: it is
  a mouth on the connection it already has. shape ported from prixie's voice branch.
- **screenshare**: `getdisplaymedia` from inside the spawnable, which is verified
  working (headed chrome under xvfb, https context, whole-screen auto-select). the
  browser shares; nothing is re-streamed through us.

refused: recording without a participant knowing, and publishing the recording. it
renders, never publishes.
