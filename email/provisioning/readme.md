# provisioning: getting the address before there is anything to read

the lane in the folder above is the front door: it receives, checks a signature and a whitelist, and
writes one envelope. this folder is the step before that, which is getting an address on a domain
someone controls. two providers do it here, and they are close enough in shape to be one decision and
far enough apart in detail to be two pages.

the short version, because the choice is small:

| | carlyemail | agentmail |
| --- | --- | --- |
| free tier | 3 inboxes and 1,000 emails a month, no card | free for `@agentmail.to` addresses; a paid plan for a custom domain, and the figures are not recorded here |
| custom domain on the free tier | **yes** | **no**: a custom domain is a paid-plan feature, so the free tier is `@agentmail.to` addresses only |
| address shape | `[name]@yourdomain.tld`, or `[name]@subdomain.yourdomain.tld`, free | the same shape, on a paid plan; free is `[name]@agentmail.to` |
| inbound signature | svix, `whsec_` secret, `v1` over `id.timestamp.body` | a plain shared header, `x-agentmail-secret` |
| our gate | `CARLYEMAIL_SIGNING_SECRET` | `HEYPHONY_MAIL_SECRET` |
| subdomains | `subdomains_enabled`, one wildcard MX on `*` | `subdomains_enabled`, one wildcard MX on `*` |
| dns records | 3 dkim cnames, spf txt, bounce mx, dmarc txt, inbound mx | the same set, plus a downloadable bind zone file |
| zone import | `carlyemail domain <name> --zone` | download the bind zone file from the console |

## why the custom domain is the part that matters

the free tier is where the two providers stop being one decision. carlyemail puts a custom domain on
it; agentmail does not, so an agent on agentmail's free plan sends from `@agentmail.to` and the
agent's own name is a paid feature. that single line is why the recommendation is carlyemail first and
agentmail later, if at all.

an address on a shared domain is fine until the day it is not: the reputation belongs to everyone else
using that domain, and there is nothing to retire if something goes wrong. an address on a domain you
own is the agent's own name, in the agent's own brand, with a reputation that is yours to keep clean.

which is where the naming lands: if the agent has a name, the address should carry it. `[name]@yourdomain.tld`
reads like a person's mailbox, and `[name]@agents.yourdomain.tld` reads like a mailbox on a domain the
owner can retire without touching the mail that humans use. both providers support the second shape
with a single wildcard record, and both treat a subdomain inbox as sharing its parent's sending
reputation, so the subdomain is a blast-radius decision rather than a second brand.

the one trap both providers warn about, in their own words: **do not put the inbound MX on the apex**
of a domain that already receives human mail. a subdomain is the shape that cannot break the mail
someone already reads.

## the order of operations

1. own a domain, or a subdomain of one, and be able to publish dns for it.
2. create the domain at the provider, with `subdomains_enabled` if the pattern is `[name]@sub.domain`.
3. publish the records the provider returns. import the zone file if the dns host can take one.
4. verify, and read the per-record status rather than an overall yes or no: both providers report each
   record separately, which is what makes a stuck domain explainable.
5. create the inbox, and set the provider's signing secret as the gate in the lane above. an unset
   secret closes the door rather than opening it.
6. send one message from outside and watch it land. an inbox that has never received anything is not
   proven, and this branch's evidence fields say so.

## what is not here

no outgoing relay beyond `SMTP_URL`. the lane can receive and normalise mail today; sending is the
narrow part and it is narrowed on purpose, because a mailbox that answers on its own is a mailbox that
can answer wrong.
