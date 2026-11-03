# slack

the events api, which is the cleanest of the chat lanes: slack signs every delivery
with the same `v0` scheme imessage uses, so the gate is already written.

wired: intake (`x-slack-signature` over `v0:timestamp:body`, five minute
freshness), a url verification challenge answer, and replies through
`chat.postMessage` with a bot token.

not wired: the app install flow. creating the app and granting scopes is a human
act in a browser, once.

gate: `SLACK_SIGNING_SECRET` in, `SLACK_BOT_TOKEN` out.
