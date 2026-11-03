# bitcall

not a phone number vendor, which is why it is in the table and why it has no hook.

## what their api actually is

`docs.bitcall.io` documents otp, esim and hlr lookups. that is a verification and mobile identity api, not a number you can be texted on. their own integration guides for voice and assistant platforms describe inbound dids as coming soon, which is a phrase with no date on it.

so this row exists for a specific reason: it is easy to see a telecom api with an otp endpoint and assume the number comes with it. it does not.

## what that means for the repo

- **no text rail.** `text_style` is `none`, and there is no route, because there is nothing to receive.
- **no outbound.** no outbound sms claim.
- **the sip registration half is what applies**, if and when the did product ships: the config writer does not care who sold the number.

## outbound

**no outbound sms claim.** an otp and hlr api has no message to send to a person, so there is nothing here to wire. the row in `heyphony send --paths` exists to keep the answer short for anyone who assumed otherwise.

## the honest limit

this is the one page in the folder that is mostly a warning. the api is real, the numbers are not, and an agent tasked with "get me a number" that wanders into this documentation will come back believing it found one unless something says otherwise. this page is that something.

## where it genuinely fits

otp and hlr lookups are how a legitimate workflow checks whether a number is real and reachable, and that is a different job from being reachable. if you later need to know what line type a number is, this is the kind of api that answers it, and it has no business being on the receiving side of this package.
