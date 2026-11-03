# questblue

a trunk rather than a registration, which changes what a "number" means here.

## a trunk, not an account

most of the vendors here hand you a sip username and password and the client registers to their server. questblue sells a trunk: the number is routed to a pbx-shaped endpoint you own, and `sip_style` says `trunk-route` rather than `registration`. it works, and it is a different mental model. if you are pointing baresip at it, the outbound proxy and the number presentation are the parts to get right, and the number is not "registered" anywhere.

## how texts arrive

a `POST` to a url you set, configured by a `PUT` to `https://api.questblue.com/smsv2` with `sms_mode=url` and `post2urlmethod=json`. basic auth with `QUESTBLUE_API_USER` and `QUESTBLUE_API_PASS`, plus a `Security-Key` header from `QUESTBLUE_API_KEY`, which is three credentials where most of these want two.

`heyphony hooks questblue --apply --did +1...` renders that call and refuses if any of the three variables is missing, because a half configured hook is worse than an unarmed one: it looks armed in a portal and silently drops the text.

## outbound

**gateway not wired.** `smsv2` is documented for inbound delivery as a url post, and the send direction on that same endpoint is a mode this repo has not read closely enough to build against. the row says so instead of guessing a field name.

## what is still unverified

the whole vendor: nobody has bought a number here, and a trunk is the kind of thing whose first problem only appears when a real call arrives with the wrong codec or an unexpected caller id.

## setup sketch

1. `QUESTBLUE_API_USER`, `QUESTBLUE_API_PASS` and `QUESTBLUE_API_KEY` in the environment
2. buy the number, then create the trunk and point the number at it
3. `heyphony hooks questblue --apply --did +1... --base https://your-host:8099`
4. `heyphony connect sip --provider questblue --did +1... --username ... --password ...`
5. text it, then `heyphony inbox`
