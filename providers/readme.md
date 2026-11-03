# providers: the number comes before the vendor

*the pages beside this one are per vendor notes. this page is the question that comes first: what your workflow actually does, and therefore which kind of number you can get.*

a phone number is not a feature you buy, it is a classification somebody else applies. carriers and the services that verify numbers ask "what is this" and answer from the numbering plan of the country that issued it, so the same agent on the same stack gets accepted with one number and refused with another. that is why this page starts with the workflow and the region, and only then reaches the vendor list.

## what kind of number each workflow needs

### the table

| how heavy the workflow is | what it is actually doing | the number it needs | country | prefix | price band | what gets refused |
| --- | --- | --- | --- | --- | --- | --- |
| heaviest: an identity on a messaging app | holding a whatsapp, signal or google account that verifies by sms, and keeping it | a number the app reads as a **mobile**, which in practice means a virtual mobile number rather than a did | united kingdom | +44 | standard | 01 and 02 ranges. a uk landline prefix is the same order form and the wrong product |
| heaviest: an identity on a messaging app | the same | the same | sweden | +46 | standard | a geographic fixed line |
| heaviest: an identity on a messaging app | the same | the same | lithuania | +370 | standard | a geographic fixed line |
| heaviest: an identity on a messaging app | the same | the same | poland | +48 | standard | a geographic fixed line |
| heaviest: an identity on a messaging app | the same | the same | australia | +61 | pricier | a geographic fixed line |
| heaviest: an identity on a messaging app | the same | the same | netherlands | +31 | pricier | a geographic fixed line |
| heaviest: an identity on a messaging app | the same | the same | united states, canada, all +1 | +1 | cheapest | all of it. cloud numbers, softphones and trunks share one bucket, and the large services read that bucket as voip |
| heavy: receiving most of the traffic | a number humans call and text, with an inbox an agent reads | any sms capable did, on a provider that will arm an sms webhook | any of the vendor countries | whatever the vendor stocks | the vendor's | a number from a vendor that only does voice. a calls only number cannot receive a text, and no amount of cli fixes a webhook the carrier will not call |
| medium: occasional outbound at human pace | one call or one message at a time, to somebody who expects it | the same did as above, ideally from a vendor that lets you set the caller id and read delivery reports | any | the same | the vendor's | anything bulk. a2p consent, attested origination and a registered business are the real requirements, and this repo refuses that lane rather than pretending a cheap did solves it |
| light: proving a lane works | one real call and one real text to confirm the setup | the number you already bought, or a vendor's test line | wherever you signed up | the same | already paid | nothing, but do not build a workflow on the trial |
| none: codes and verification at volume | signing up for things by sms | none of these numbers. a did is voip, and voip is the classification that gets refused | nowhere | none | not applicable | this whole repo. there is no otp story here and buying a number will not create one |

the country rows carry the price band the owner sorts by: the united kingdom, sweden, lithuania and poland are the standard band, australia and the netherlands are the pricier one, and every row above a +1 number costs more than the +1 number while being the only ones that work.

### a uk number is a range, not a country

"get a uk number" is not an instruction. inside +44 the range decides whether the text lane exists at all, and the ranges are sold on the same order form for the same monthly price:

| prefix | what the range is | can it receive a text |
| --- | --- | --- |
| 07 | mobile, the range a virtual mobile number is issued in | yes, and this is why the uk row works |
| 03 | uk-wide business numbering | usually, and it is worth confirming per carrier before paying |
| 01 and 02 | geographic landlines | mostly not. the number dials, the text does not arrive |
| 056 | the uk's own range for voip services | no, and it is the one prefix that announces what it is |
| 070 | personal numbering, which redirects a call | no. it moves a call and holds no text |
| 08 and 09 | service and premium ranges | no, and 09 is never a number a person texts |

so the two orderable prefixes are **07** and **03**, and `heyphony setup provision --numbering GB` prints that answer with the range table instead of leaving a person to find out after the number is bought. `heyphony connect sip` reads the did you gave it and says the same thing about that number.

### why the region decides more than the vendor

**classification rides the numbering plan, not the marketing.** two vendors can sell you a number in the same country and it will be treated the same way, because the thing that answers the "what is this" question is the regulator and the carrier, not the invoice. that is also why moving up a page to a more expensive vendor does not change what your number is, and why the cheap option and the expensive option are often the same classification wearing different dashboards.

for the messaging app case the ordering is roughly: the united kingdom, sweden, lithuania and poland read as mobile for the large services at the standard band, australia and the netherlands read the same way at the pricier one, and +1 is the row to avoid when the far end is a consumer service running a risk engine.

### the two kinds of number, in one line each

- **a did** is a number in the public telephone network that you register on a host you run. calls and texts both, over sip, and it is the only kind this repo registers.
- **a virtual mobile number** is a number that lives inside a provider's web application and behaves like a mobile handset. it cannot be registered in baresip or linphone, so it is a different job from the one here: useful for holding an account, useless as a line an agent answers.

mixing those two up is the most expensive mistake available on this page, because a virtual mobile number looks like a phone number and behaves nothing like a sip endpoint.

## the vendors on the pages beside this one

| vendor | what it is good at | the catch |
| --- | --- | --- |
| [voip.ms](voip.ms/readme.md) | cloud voicemail to email, sms to email, conditional forwarding, all of which work while the host is asleep | regional servers matter, and a wrong one is the classic silent registration failure |
| [flowroute](flowroute/readme.md) | json webhooks for inbound texts, which arrive whether or not anything is awake | no carrier side voicemail fallback, so a missed call is just missed |
| [anveo](anveo/readme.md) | the only vendor whose whole chain has a documented api: order, arm the hook, list | the send gateway's parameter names are inside their account portal |
| [signalwire](signalwire/readme.md) | the cheapest number here, a clean json payload, a wired send path | inbound texts are billed, at a fraction of a cent each |
| [questblue](questblue/readme.md) | a url post for inbound, documented and armable by one call | a trunk rather than a registration, and three credentials rather than two |
| [bulkvs](bulkvs/readme.md) | six cents a month, with an openapi document sitting next to the docs | carrier shaped documentation, and your first number is not a product walkthrough |
| [jmp.chat](jmp.chat/readme.md) | mms and transcribed voicemail arriving in a chat client, no webhook needed | the chat client is the receiver, so the inbox depends on a client staying up |
| [voyced](voyced/readme.md) | european geographic numbers billed per minute inbound | no sms claim, and their own docs call the api unfinished |
| [voxacall](voxacall/readme.md) | a sip trunk bought with crypto and no identity paperwork | no public sms documentation, so there is nothing to build against |
| [bitcall](bitcall/readme.md) | otp and hlr lookups, which is a different job from being reachable | it is not a number you can be texted on, and their dids are still "coming soon" |

a page per vendor, because a table with ten rows and two pages was hiding eight of them. the pages are notes from reading each vendor's own documentation, not reviews, and the honest state is one provider at a time.

## we are not affiliated with any of them

none of the vendors above pay for this, none of them are partners, and nothing here is a referral. the same is true of every piece of software this repo leans on, which is worth saying out loud because a page that names a client as often as this one does can start to look like a partnership:

- **linphone**, by belledonne communications sarl, is the softphone whose config format this repo writes. the authors have never heard of this repo and owe it nothing. the rail works because their format is documented, not because of an arrangement.
- **baresip**, by its own authors, is the host client the call lane drives over a json socket. same relationship: a documented protocol and a licence we read, nothing more.
- **the carriers themselves**, voip.ms, flowroute, anveo, signalwire, questblue, bulkvs, jmp.chat, voyced, voxacall and bitcall, are rows in a table. naming a vendor is a description of their published api, not a partnership, an endorsement or a reseller agreement.
- **the platforms the number then gets used on** are not involved at all. an agent texting a signal contact or reaching a zoom invite is using software nobody in this repo represents.

the send rail follows the same rule. three providers are wired to the api call their own docs describe, and the seven that are not say so in `heyphony send --paths` with the reason and the docs link, because a page that lists ten vendors should not imply ten doors are open. no links carry an identifier, no prices are quoted on their behalf, and where a price appears it is the one the vendor published on the day it was read, which is a number that moves.

the same applies to what the notes claim a vendor can do. a capability is written down because their own documentation says it, and the flags that matter stay unverified until somebody pays for a number and watches a message arrive. documentation is not experience, and a vendor can change a feature out from under a page like this one without telling anybody.

if a vendor disappears, the lane closes and the number goes with it. the registration, the inbox and the call log are yours because they live on your host, and that is the part this repo can promise. the carrier is somebody else's computer, and it always was.
