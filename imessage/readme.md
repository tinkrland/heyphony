# imessage

blue bubbles, through photon (spectrum posts every inbound message to a webhook).
no mac required in the house: the provider holds the bridge, which is the only
reason this lane is possible at all from a linux box.

## not a beast, on purpose (owner, nov 2026)

imessage is the one lane we deliberately do not build. photon's free tier, pointed at
whitelisted people, is the whole commitment: no mac mini in a closet, no bridge of our own,
no number ownership attempt (a voip did cannot register imessage, so there is nothing to
attempt). rcs is the fallback when a contact has no blue bubble, and behind both of them sits
the real floor, a plain sms on the heyphony did.

that ordering is the design, not a compromise. if photon's free tier goes away, this lane
closes and sms keeps working, which is why the pile underneath it is a sip did and not an
apple id. bragging rights are earned by the boring layers.

wired: the gate. `v0` hmac over `v0:timestamp:body`, verified against the raw body
before parsing, five minute freshness, then a number whitelist (e.164). sending
uses the provider's own endpoint and fails closed without project creds.

not wired: reactions, tapbacks, attachments beyond the text. an email-addressed
imessage sender works, and is normalised like any other.

gate: `PHOTON_SIGNING_SECRET` in, `PHOTON_PROJECT_ID` + `PHOTON_PROJECT_SECRET` out.
