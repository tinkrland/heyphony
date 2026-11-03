# flowroute

free inbound messages, and the honest split that comes with them.

## texts arrive somewhere else entirely

flowroute delivers inbound sms over its **http api (webhooks) or smpp**, not over sip. linphone therefore never sees them: there is no sip message to receive, and pointing linphone at flowroute expecting texts is a category error.

so texts need a catcher. `heyphony serve` is that catcher: it listens for flowroute's delivery callbacks, appends them to the local inbox, and can forward each one to an email address. this is a *feature*, not a workaround:

- the message is stored by the proxy, so it is safe **even when the machine is not running**
- the inbox is jsonl on disk, so a later agent reads it without any network at all
- forwarding to email means the owner sees it in the place they already look

## calls are plain sip, and they die with the machine

inbound calls arrive as sip invites to the registered endpoint. no registration, no call: if the vm is off or the agent is paused, the call fails at flowroute and there is no cloud answering machine in this setup. that is the trade for the free texts.

mitigation is on the card, not in this repo's imagination: keep the keeper registered on the host (see the telecom line's duty-cycle notes) or accept that a sleeping machine misses calls. do not claim voicemail here, because flowroute is not recording it for you.

## outbound

**wired.** `heyphony send --provider flowroute --to +1... --text "..." --send` posts their `v2.2/messages` envelope, json with a `data.attributes` body of from, to and body, authenticated as basic with `FLOWROUTE_API_KEY` and `FLOWROUTE_API_SECRET`. delivery reports come back as a webhook to the same catcher that receives the texts, which is the one place flowroute's shape is tidier than voip.ms.

## setup sketch

1. order a did with sms enabled, note the sms-enabled flag, not just the number
2. point the number's inbound sms webhook at `https://<your-host>/flowroute` and set `--token` to something only you know
3. point the number's voice route at your sip registration host
4. `heyphony connect sip --provider flowroute --did ... --username ... --password ...`

prices are the owner's number, not a quote: about a dollar a month, incoming messages free. per-message and per-minute rates exist and change; check the dashboard before promising anything to anybody.
