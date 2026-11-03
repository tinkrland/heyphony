# voyced

european geographic numbers, sold as voice, with an api that is honest about being unfinished.

## the number

geographic dids across europe and beyond, around two and a half pounds a month in their web store, with inbound charged per minute rather than included. that pricing shape tells you what the product is: a business line for a small office, not an inbox for a program. per minute inbound is fine for a number that rings occasionally and expensive for one that rings all day.

## the honest part

their own knowledge base describes the api as in active development and under controlled testing. that is unusually candid, and this repo takes it at face value: `text_style` is `none`, no sms capability is claimed, and nothing here is built against an endpoint that might not exist next month.

## what that means for the repo

- **voice only.** a number that can be dialled and can ring a sip endpoint, which is the half of this package that needs no webhook.
- **no hook, and no row pretending otherwise.** the catcher will not accept `/sms/voyced` because there is nothing to send it.
- **no outbound.** `heyphony send --paths` says no outbound sms claim, which is a statement about their product rather than about this repo's willingness.

## outbound

**no outbound sms claim.** their product is a voice line, and an api still under controlled testing is not a place to build a send rail. `heyphony send --to ... --provider voyced` refuses and says so, which is the same answer their own documentation gives.

## when it would move

if the api leaves controlled testing with sms and a documented hook, this page changes and a route gets a row. until then it is a voice number in europe, and european geographic numbers are also worth knowing about when a workflow wants to look local.

## setup sketch

1. order the geographic number in their web store, in the country you actually want to look local to
2. `heyphony connect sip --provider voyced --did +1... --username ... --password ...`
3. place a real call and listen to it, because a per minute number that nobody has dialled is a router configuration, not a phone
