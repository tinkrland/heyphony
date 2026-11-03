# locale: where a number is bought changes what it is

the country on a number is not decoration and not a preference. it is the field that decides what
class the number belongs to, and every service that guards signup reads that class before it reads
your ip address.

## a number is a legal object before it is a technical object

a telephone number is issued out of a national numbering plan. the plan says which ranges exist, who
may hold them, and what a call to one of them is expected to reach. when a numbering plan gives cloud
providers mobile ranges, the provider's number is a **mobile number**, with everything that follows:
it receives sms, it has a mobile prefix, and a service looking at it sees a phone.

when a plan keeps a single bucket for everything that is not a carrier's own sim, the same provider
selling the same product issues a **did**, and a service looking at it sees a number that terminates
somewhere other than a handset.

same software, same price range, different class. the word for the class in the uk is a virtual mobile
number, and the category exists because the regulator expects the provider to behave like a carrier.

## the list, and why it is short

| country | prefix | what a cloud number is there | signup-class services | band |
| --- | --- | --- | --- | --- |
| united kingdom | +44 | virtual mobile number, a mobile range issued to a provider | accepted | standard |
| sweden | +46 | mobile number | accepted | standard |
| lithuania | +370 | mobile number | accepted | standard |
| poland | +48 | mobile number | accepted | standard |
| australia | +61 | mobile number, issued the same way | accepted | pricier |
| netherlands | +31 | mobile number | accepted | pricier |
| united states, canada, +1 | +1 | a did, one bucket for cloud, softphone and trunk | refused | cheapest, and the wrong tool |

the bands are the owner's sorting, not a price list: the united kingdom, sweden, lithuania and poland are the standard band, australia and the netherlands are the pricier one, and everything in the standard band still costs more than a +1 number, which is the number that does not work.

the last row is the one people buy first because it is a dollar and it arrives in a minute. it is also
the row that fails at the exact moment the number matters.

## the prefix is the product, not the country

within the united kingdom the country code is not enough to answer the question, because +44 contains ranges that behave nothing alike and they are sold on the same form for the same monthly price. 07 is a mobile range, which is the one a virtual mobile number is issued in and the reason the uk row works at all. 03 is uk-wide business numbering and is usually text capable. 01 and 02 are geographic landlines, and most of them cannot receive a text: the call connects and the message simply never arrives. 056 is the uk's own range for voip services, and 070 is personal numbering, which redirects a call rather than holding a message.

so the orderable prefixes are 07 and 03, and the answer for a country is a range rather than a country. `src/setup/numbering.py` is where that lives as data, `heyphony setup provision --numbering GB` prints it before anything is bought, and `heyphony connect sip` applies the same reading to the number somebody already holds.

## it is the law, not a trick

nothing in the list above hides anything. the number is not spoofed, the location is not faked, the
device is not disguised, and no account is being made second-hand. a uk or polish or lithuanian cloud
number **is** a mobile number, and buying one is buying a mobile number.

this matters for how the work is described, not only for how it is done: there is no trick to explain
away, no rule being bent, and no reason to route the traffic through another country to make it look
right. picking the country is picking the class.

## two numbers, two jobs

the country answer is the same for both, and the products are not interchangeable:

- **the line.** a sip did from voip.ms, anveo, bulkvs or jmp.chat, in one of the countries above, is
  real sip. it registers on the host, receives its texts into heyphony, and rings while the machine is
  up. this is the number the agent answers on, and the one `heyphony setup select sip` is for.
- **the signup number.** a web-hosted number such as fanytel is not sip and cannot be registered in a
  softphone. it exists to receive one code so an account can be created, and after that it can sit
  there. the whatsapp lane carries that path, because that is the lane it is for.

choosing wrong is the common mistake in both directions: buying a signup number for a line that has to
ring, or trying to make a line pass a signup it will fail.

## what this changes in the setup

`heyphony setup select sip` asks for a provider and a did, and it does not ask for a country, because
the number is already issued by the time you are registering it. what the country of that did decides
is the thing setup cannot change, so the honest place to read it is here, before the number is bought,
rather than in `doctor` afterwards.

the lookup that does belong in the flow is the other half: which area codes inside a country have
stock, and what a month of each costs. that is `heyphony setup areas`, and it exists because "some
number in your country" is not a decision an agent can make on its own.
