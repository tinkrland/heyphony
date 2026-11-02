# vendors

*ten number shops, sorted by the only question that matters*

the question is not price, and it is not "does it have an api". it is: **when somebody texts this number, does anything arrive, and can a process read it.** a provider that cannot answer that is selling you a voice number with a phone-shaped website, and a provider that answers it in an unusual way is fine as long as you know what the unusual way is.

seven of the ten answer yes. three answer no, and they are listed anyway, because "i sell eu dids" and "i can be your inbox" are different sentences and it is worth seeing them side by side.

## the table

| provider | numbers | a month | how a text reaches us | api for ordering |
| -------- | ------- | ------- | --------------------- | ---------------- |
| voip.ms | us, ca | $1.00 | email, carrier side sms-to-email | yes |
| flowroute | us, ca | $1.00 | a json webhook, and never sip | yes |
| anveo | us, ca, uk | $0.99 | a url with `$[from]$` and `$[message]$` spliced into it | **yes, the whole chain** |
| signalwire | us | $0.50 | a swml message handler posts json | yes |
| questblue | us | $0.70 | per number post to url, fields from, to, msg | yes, after a stock question |
| bulkvs | us, ca | $0.06 | one webhook registered in the api, attached per number | yes, npa/nxx inventory |
| jmp.chat | us, ca | $4.99 | a jabber message to your jid | ad-hoc commands only |
| voyced | eu, worldwide | about 2.50 | nothing: no sms on a geographic number | in controlled testing |
| voxacall | global | ask | nothing: trunking and dids, no sms story | behind a login |
| bitcall | global | ask | nothing yet: inbound numbers are on their roadmap | otp, esim, hlr only |

prices are the ones each provider publishes on its own pages, and every value is `verified: false` in `src/providers.py` until a real delivery proves it, because a phone number that has never received a message is not a phone number that works.

## the seven that can be an inbox

**voip.ms** is the patient default. carrier side voicemail, sms-to-email, conditional forwarding, and all of it keeps working while the host is idle or off. it is the provider you pick when you want the machine to be able to be asleep, and the one whose dashboard is old enough to be predictable. texts arrive through the email lane, which means the email lane is doing double duty here.

**flowroute** is the developer default. inbound sms arrives over their http api or smpp, never over sip, which is a plus for exactly the same reason: the webhook catches it whether or not a client is registered. what it does not have is a carrier voicemail fallback, so a caller who reaches nothing gets nothing. that is a fact about the provider, not a bug in the lane, and the readme's offline matrix says so in the cell where it matters.

**anveo** is the one that is actually scriptable end to end, which is why it is the only provider with a `heyphony setup provision` path. `ANVEO.AREAS.LIST` gives stock and prices per area code, `DID.ORDER` places an order, `DID.UPDATE` sets `SMS_URL` by e164 to the url the catcher already listens on. sms works on us, ca and uk numbers, which is the only uk inbox in this table.

**signalwire** is the cheapest number that still behaves, at fifty cents, and its inbound sms is not free but close (roughly a third of a cent). a swml message handler posts one json object with `message.from`, `message.to`, `message.body` and a `message_id`. you choose the sip credentials instead of being issued them, which is nice.

**questblue** is a trunk provider: the number routes at your trunk and sms posts to a url you set over their api. good if you already think in trunks, slightly more moving parts if you do not.

**bulkvs** is the wholesale row, six cents a month with inbound sms at a third of a cent and no minimum. one webhook registered in the api, then attached per number. the api is real and documented, including a per-number `Webhook`, `Sms` and `Mms` field.

**jmp.chat** is the odd one and the most agent-shaped. five dollars a month buys unlimited texts and picture messages plus voicemail delivered as audio *and a transcription*, all of it arriving as jabber messages to your jid. there is no webhook anywhere, which means the receiver is a client on the host rather than a url, and that is the one row here whose wiring is a small piece of work rather than a paste.

## the three that cannot receive a text

**voyced** sells eu and worldwide geographic dids, priced per country, billed per minute inbound, with a genuinely useful coverage map. nothing they publish claims sms on a geographic number, and their own knowledgebase says the api is in active development and controlled testing. treat it as a voice only number until a real text lands on one.

**voxacall** is no-kyc, crypto-paid sip trunking aimed at call centres: quick to open, no public sms story, and the exact shape a recipient's risk engine blocks first. it is a voice option, not an inbox.

**bitcall** has the cleanest api of the three and the cleanest answer, which is that inbound numbers are coming soon. the documented api is otp, esim and hlr. an outbound trunk cannot be an inbox, so it stays parked until their dids ship.

## two corrections worth writing down

**bulkvs does not appear to do uk.** it was described to us as covering the uk, and nothing on their site backs that: their number search is npa and nxx, their pricing says us and canadian, and their api orders from north american inventory. it is still the cheapest row here by an order of magnitude, so if uk coverage turns out to exist behind the login, the table changes.

**jmp.chat's receiver is a client, not a route.** texts and voicemail arrive as xmpp messages to a jabber account, so there is no url to paste and `heyphony hooks jmp.chat` says exactly that. onramping it means running a jabber client on the host and bridging what it receives into the inbox, which is a day of work rather than a setting.

## what survives the machine being off

| provider | texts while off | voicemail while off | live calls while off |
| -------- | --------------- | ------------------- | -------------------- |
| voip.ms | yes, sms to email | yes, carrier voicemail to email | no |
| flowroute | yes, our webhook stores them | no fallback at the carrier | no |
| anveo | yes, a url forward at the carrier | yes, call flow voicemail | no |
| signalwire | yes, the swml handler posts | no mailbox we rely on | no |
| questblue | yes, the number posts to a url | no fallback | no |
| bulkvs | yes, one api webhook | no fallback | no |
| jmp.chat | yes, jabber holds it | yes, transcribed to jabber | no |

texts never travel over sip. that single sentence explains the entire first column, and it is the reason an inbox is a provider feature rather than a client feature. voicemail is a carrier feature, so it exists when the carrier offers one and not otherwise. live calls need a registered endpoint, so they are the one thing that genuinely stops when the host sleeps.

## ordering a number, and where the money stops

ordering is a browser errand for nine of the ten, and the setup plan says so rather than pretending otherwise. anveo is the exception, and even there the chain is deliberately split: area stock and prices are free to ask for, `DID.ORDER` is not, so `heyphony setup provision` builds the order and **stops before it spends money**. the last step is a person's, because a purchase is a purchase.

```
heyphony setup provision --provider anveo --areas --country-id US     # stock and prices, free
heyphony setup provision --provider anveo --area-code 212             # the exact order call, unrun
heyphony hooks anveo --apply --did +12125551234                       # arm texts on a number you own
```

area selection is first class because "some number in your country" is not good enough for a human who will be called back on it: `--country-id`, `--state-id`, `--area-code` and `--area-name` all reach the same `ANVEO.AREAS.LIST`, and the answer carries stock plus what each rate plan costs in cents a month.
