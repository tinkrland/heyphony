# lookup: what the number is, from evidence

*this folder answers one question about a number before anybody spends money on it: what class of line is this, and what follows from that class.*

this is evidence, not a verdict, and it is built from **numbering plans**, not from a carrier, because a numbering plan is the only thing that is both public and stable. ofcom publishes which uk ranges exist and what each one is issued for, and the same is true of most european regulators. that evidence is enough to answer the two questions people actually ask:

- **what type of line is this**: mobile, landline, business numbering, a voip range, personal numbering, a pager, a service range.
- **can it receive a text**: for most ranges this follows directly from the class, and where it does not, the answer is `unknown` rather than a guess.

## what it will not answer, and why that is the honest position

a lookup that says `whatsapp: true` for a number is not reading a numbering plan. it is either texting a code to somebody else's handset or talking to an unofficial endpoint with a borrowed token, and both of those are actions against a real person's phone rather than a read of public data.

`unknown` is a first-class result here, and an answer that the plan cannot give is `unknown` rather than
a guess.

so the service support matrix in `support.py` is **evidence-shaped**: for each service it says what the line class implies (`a landline cannot register any of them`), what the numbering plan cannot tell you, and the exact probe each service would need if you decided to run one. `heyphony --lookup <number> support` prints that, with `unknown` where the truth is unknown.

the probe plan is printed and not executed. each entry names its consequence:

- a registration probe **sends an sms code to that handset**, which is a stranger's phone ringing for a check nobody there asked for.
- the unofficial presence endpoints for the three large services are undocumented, rate limited, and change without notice, so a `false` from one of them is a fact about the endpoint that day.

## the shape of an answer

    $ heyphony --lookup +15373832662
    { "number": "+15373832662", "valid": true, "market": "US", "type": "unknown", ... }

    $ heyphony --lookup +442071234567
    { "number": "+442071234567", "valid": true, "market": "GB", "type": "landline",
      "receive_text": false, "region": "london", ... }

every answer carries `evidence` (what the classification rests on, with the regulator and the date), `limits` (what the answer cannot say), and `verified` (false until a real number from your own corpus agrees). an `unknown` is a first-class result: it means the market's plan does not encode the answer, which is exactly true of the north american numbering plan, where line type is a carrier question and never a range question.

## coverage, stated per market

- **gb**: per range, verified against ofcom's numbering data. this is the market this repo is actually good at, down to `070` being personal numbering rather than mobile.
- **us and ca**: `line type is a carrier question` for every number, because the nanp does not encode it. the honest output is `type: unknown`, with the reason spelled out.
- **se, pl, lt, nl, au**: market level evidence only: the country's cloud numbers are issued in mobile ranges. that answers "is a number from here the right class", never "is this particular number a mobile".
- **everything else**: `unknown`, with the market named as unseeded. guessing a line type from an unfamiliar plan is how a lookup tool starts lying politely.
