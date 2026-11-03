# voxacall

crypto paid sip trunking with no kyc, which is a real feature and an unusual one.

## what it is

a trunk, so `sip_style` is `trunk-route` and the number is routed to an endpoint you own rather than registered to their server. payment in crypto, no identity paperwork, a developer api that appears behind registration. for somebody who wants a pstn leg without handing over a passport, that combination is the entire appeal.

## the trade, stated plainly

no public sms documentation, an api you cannot read before signing up, and a support surface that is a chat channel rather than a portal with a ticket queue. this repo can describe that honestly and cannot verify it: there is nothing to read from outside.

## what that means for the repo

- **voice only.** `text_style` is `none`, there is no hook, and the catcher will not accept a `/sms/voxacall` path.
- **no outbound.** no outbound sms claim.
- **the config half still works**, because sip is sip: `heyphony connect sip --provider voxacall --did +1... --username ... --password ...` writes the client config the same way it does for everybody else.

## outbound

**no outbound sms claim.** there is no public send documentation to build against, and a rail written from memory is a rail that fails on somebody's real phone. voice only, and the refusal names the reason rather than a generic no.

## when it would move

if their docs become public and include sms with a hook, this becomes one more row with a route. until then it is the vendor you choose when the reason is payment rather than features.

## setup sketch

1. register, pay in crypto, get the trunk credentials
2. attach a number to the trunk and note the outbound proxy
3. `heyphony connect sip --provider voxacall --did +1... --username ... --password ... --server <outbound proxy>`
4. place a real call before trusting the number with anything
