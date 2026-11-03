# streaming

twitch and kick. the one folder where the rule flips: everywhere else "renders,
never publishes" holds, and here publishing *is* the product, so the rule becomes
"the human presses go live and the agent never does".

- **twitch**: rtmp/rtmps ingest with a stream key, helix api for title and category,
  and obs driven over obs-websocket. all of it official.
- **kick**: rtmp ingest with a stream key works today. the api is unofficial, so this
  folder refuses api calls rather than scraping a dashboard with borrowed cookies.
  a stream key or nothing.

the screenshare and scene work belongs to meetings/ and to obs; nothing here encodes
video twice.

gate: `TWITCH_CLIENT_ID` + `TWITCH_CLIENT_SECRET` for the api, `KICK_STREAM_KEY` for
ingest. the go-live press is not a gate and never becomes one.
