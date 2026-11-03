# signalwire

the cheapest number of the ten, and the most expensive text.

## the shape of the deal

fabric sells numbers as rest resources, and a number alone is around fifty cents a month, which is the lowest did price in this table. inbound sms is not free here, at roughly a third to two fifths of a cent per message. for a number that receives a few texts a day that is nothing; for a page that promises a free inbox it is a different promise than voip.ms makes, and worth knowing before the number is bought rather than after.

## how texts arrive

a json webhook from their swml handler, posting a payload shaped like `{"message": {"from", "to", "body", "message_id", "timestamp"}}`. that is a clean shape with an id in it, so duplicate deliveries dedupe properly.

the hook is `webhook-json`, and this is the one vendor whose apply descriptor says **dashboard or fabric rest**: the resource path that arms the handler is not pinned here, so the arming step is manual or your own call. the catcher side is wired either way.

## outbound

**wired.** `heyphony send --provider signalwire` builds the laml messages call for your space, `POST https://<space>.signalwire.com/api/laml/2010-04-01/Accounts/<project>/Messages.json` with basic auth of project and token, form encoded `From`, `To`, `Body`. environment: `SIGNALWIRE_SPACE`, `SIGNALWIRE_PROJECT`, `SIGNALWIRE_TOKEN`.

## what is still unverified

the inbound payload shape is from their docs, and no message has been sent through the laml rail here. a provider can change a feature under a page like this without telling anybody, which is why `verified` stays false in the data until a real message lands.

## setup sketch

1. `SIGNALWIRE_SPACE`, `SIGNALWIRE_PROJECT` and `SIGNALWIRE_TOKEN` in the environment
2. buy a number in fabric, confirm sms is enabled on it
3. point the number's handler at `https://your-host:8099/sms/signalwire`, carrying the catcher token
4. `heyphony connect sip --provider signalwire --did +1... --username ... --password ...`
5. send yourself a text, then `heyphony inbox`
