# lookup: what the number is, from evidence

*this folder answers one question about a number before anybody spends money on it: what class of line is this, and what follows from that class.*

this is evidence, not a verdict, and it is built from **numbering plans**, not from a carrier, because a numbering plan is the only thing that is both public and stable. ofcom publishes which uk ranges exist and what each one is issued for, and the same is true of most european regulators. that evidence is enough to answer the two questions people actually ask:

- **what type of line is this**: mobile, landline, business numbering, a voip range, personal numbering, a pager, a service range.
- **can it receive a text**: for most ranges this follows directly from the class, and where it does not, the answer is `unknown` rather than a guess.

## the +1 plan does answer one thing after all: where

an earlier version of this page said the north american plan carries nothing, and that was half wrong. it
carries no **line type**, which is why `type` stays `unknown` for a +1 number. it carries a great deal
about **geography**, because the area code is assigned to a country, a territory or a region:

    $ heyphony --lookup +13405551234
    market: VI   country: U.S. Virgin Islands   region: U.S. Virgin Islands   type: unknown

`+1` is not the united states and canada. the plan is shared by **25 countries and territories**:
the us and canada, puerto rico, the us virgin islands, guam, the northern marianas, american samoa, and
the caribbean members from the bahamas and barbados to trinidad, jamaica, bermuda and sint maarten. the
table here is generated from libphonenumber's metadata (469 area codes across those 25 members)
by `tools/generate_nanp.py`, which lives outside `src/` precisely so that `src/` keeps importing nothing
but the standard library.

the area code also carries a **class**, and the class is a real answer:

- **geographic**: a region, from `New York, NY` to `Ontario`. line type still unknown.
- **non-geographic**: the plan's own national codes, which are about a service rather than a place.
- **toll-free** and **premium**: service codes. a business answers an 800 number and nobody signs up
  with one, so `receive_text: false` follows from the plan rather than from a probe.
- **personal numbering**: a follow-me number, so `unlikely` rather than a plain no.

## a field the plan cannot fill is part of the answer

an empty `region` is not a hole in the output, and leaving it unexplained is how a lookup tool trains
people to distrust it. so every answer carries a `withheld` map: the fields it did not fill, each with
the reason, and the reason is sometimes the whole point.

    $ heyphony --lookup +18005551234
    type: toll-free   region: null
    withheld.region: a toll-free code is national by design: there is no region to give,
                     and the empty region is the answer rather than missing data

a toll-free number has no region because a toll-free code is national by design. that absence is the plan
being exact, not the table being thin. the same answer names why it will not call the number a business
landline either: the line belongs to whoever answers it, so there is no personal line type to claim. the
pattern holds across the classes: a geographic +1 code withholds only the line type, a mobile range
withholds the region it never had, an area code outside the table says the table is what is missing, and a
market with no table at all withholds type, text capability and region together, saying each is
unanswered rather than guessed.

`heyphony --lookup +1800` keeps the same reasons on a partial answer, so asking for less evidence does
not make the tool quieter about what it does not know.

## a whole number is not always needed

the geography sits in the first three digits, so `heyphony --lookup +1212` answers the country and the
region from the area code alone and says that the subscriber digits were not needed. this is the same
restraint as preferring a domain to a local part: ask for the part of the number the plan actually reads,
and leave the rest on the person's side. every answer carries a `privacy` block saying what the answer
was derived from, that no request left the machine, and that nothing was stored.

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

## evidence before verdicts, which is themailtell's contract applied to a number

the shape of an answer here is deliberately the same shape as [themailtell](https://github.com/tinkrland/themailtell),
which asks the same question about an email address: independent signals with their scope, evidence
source and freshness, evidence strength with an explicit meaning rather than a made-up probability,
contradictory and unresolved states kept rather than collapsed, and `unknown` as a first-class result.

one more thing came across with the contract, and it is the reason there is an `eval`:

    $ heyphony lookup eval
    { "cases": 20, "pass": 20, "fail": 0, "unknown_rate": 0.55, "overreach": 0 }

`src/lookup/corpus.json` is a labelled fixture set, and the runner counts a claim beyond the evidence as
**overreach**, separately from a wrong answer, exactly as themailtell's runner separates false positives
from unknown rates. the fixtures were written by the same hand as the tables, so a pass proves the code
agrees with the table and **not** that the table is right about the world. no rate from this run should
be quoted as accuracy. what the run does catch is the failure that matters in a lookup tool: saying
something confident about a number whose evidence cannot support it.

the contrast pairs are the design. two numbers from one market that must not get the same answer are the
only real test that an answer is derived rather than guessed from a familiar shape, so the corpus pairs a
uk landline with a uk mobile, a geographic +1 code with a toll-free one, and a table-known area code with
one the table does not carry.

## coverage, stated per market

- **gb**: per range, verified against ofcom's numbering data. this is the market this repo is actually good at, down to `070` being personal numbering rather than mobile.
- **us, ca and the other 25 nanp members**: `line type is a carrier question` for every number, because the plan does not encode it, while country, territory and region come straight from the area code. the honest output is `type: unknown` plus a place.
- **se, pl, lt, nl, au**: market level evidence only: the country's cloud numbers are issued in mobile ranges. that answers "is a number from here the right class", never "is this particular number a mobile".
- **everything else**: `unknown`, with the market named as unseeded. guessing a line type from an unfamiliar plan is how a lookup tool starts lying politely.
