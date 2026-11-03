# bulkvs

the wholesale row. a number for six cents a month, and documentation written for somebody who already runs a carrier.

## the prices, because they are the point

- **six cents a month per number**, in the united states and canada.
- inbound sms around three tenths of a cent, outbound around six.
- a one cent enablement charge, which is the kind of line item that tells you what business this is.

for an agent that receives a handful of texts a day and nothing else, this is the cheapest way to have a real number, and it is not close. the trade is that nothing here is packaged as a product for one person: the portal is a carrier's portal, and the docs assume you know what a tn and a dlr are.

## how texts arrive

a json webhook registered per number. one `PUT /webHooks` creates the hook (`{Webhook, Description, Url, Dlr, Method}`), and then each number's `/tnRecord` carries a `Webhook` field that attaches it. so the arming is two calls, in an order that matters, and `Dlr: true` is what gets you delivery reports.

their api is at `portal.bulkvs.com/api/v1.0` and there is an openapi document at `/api/v1.0/openapi`, which is the reason this is the closest of the three unwired sends to becoming wired: the send call is written down in a machine readable place.

## outbound

**gateway not wired.** the openapi spec exists and has not been read line by line here. no field name is invented for it.

## what is still unverified

everything on this page except the prices and the shape of the two calls, both read from their documentation. no number has been bought and no webhook has been registered.

## setup sketch

1. `BULKVS_API_USER` and `BULKVS_API_PASS` in the environment
2. order the number, then enable sms on it
3. `heyphony hooks bulkvs --apply --did +1... --base https://your-host:8099`, which registers the hook and attaches it
4. `heyphony connect sip --provider bulkvs --did +1... --username ... --password ...`
5. text it, then `heyphony inbox`
