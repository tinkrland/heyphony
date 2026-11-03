# agentmail: the same shape, one dns record lighter to argue about

read from `docs.agentmail.to` in november 2026, mainly `custom-domains` and `inboxes`. the docs are
written for someone deploying many agents, which is why they are worth reading even for one: the
questions a single inbox avoids are the questions that bite at the tenth.

## the free tier does not include a custom domain

the correction that decides the comparison: **a custom domain on agentmail is a paid-plan feature.** on
the free tier the address is `[name]@agentmail.to`, which is the same shape every shared-domain
provider gives you and the same problem: the reputation is shared with every other tenant, and there is
no domain of your own to retire if something goes wrong.

everything below still holds and is still worth reading, because the domain mechanics are what you get
on the paid plan and they are the pickiest part of this whole folder. it just means agentmail is the
second choice here: carlyemail puts a custom domain on the free tier, so an agent that needs
`[name]@yourdomain.tld` today goes there.

## what the docs establish

- **`@agentmail.to` by default**, and a custom domain for production, because each domain builds its
  own sending reputation and that reputation is the single biggest factor in reaching an inbox.
- **multiple domains on purpose.** spreading volume across several domains is their recommended
  deliverability strategy, which is the opposite instinct to putting everything on one name.
- **creating a domain returns the whole record set** from the api or the console, immediately.
- **a downloadable bind zone file** for a dns host that can import one, with cloudflare's import and
  export named explicitly. transcribing records by hand is where this goes wrong, in their words too.
- **per-record verification states**: not started, pending, invalid, failed, verifying, verified. invalid
  means a record is wrong, failed means the records are right and their side needs a nudge, and those
  are different phone calls.
- **the dmarc rule**: a domain can hold only one dmarc record, an existing one should be kept rather
  than duplicated, and verification fails if it has no `rua=mailto:` reporting address. that last
  clause is the one that rejects an otherwise perfect zone.
- **an inbox is an api resource**, created with a username and a domain, and the domain may be a
  verified custom domain or a subdomain of one.

## subdomains, and what they do not give you

`subdomains_enabled` on the parent adds one wildcard MX (`*`), and then
`agent@bot.example.com` works without registering `bot.example.com` as its own domain:

- the wildcard value is a regional inbound smtp host (`inbound-smtp.us-east-1.amazonaws.com`, or the
  eu-central-1 equivalent for eu-region domains), and the console shows the exact name to use.
- if the registered domain is itself a subdomain, the wildcard is `*.mail.example.com`, so the host
  entry is `*.mail`.
- enabling it on an already verified domain returns the domain to pending, and sending is not
  interrupted while that resolves.
- **subdomain inboxes do not appear under `GET /domains`**, only under the inbox list. a provisioning
  script that lists domains and concludes there are no inboxes is reading the wrong endpoint.
- **a subdomain inbox sends under the parent's identity and dkim**, so it shares the parent's
  reputation. an isolated reputation means registering the subdomain as its own domain, which is a
  different purchase of trust and a different decision.

creating a subdomain inbox on a domain without subdomains enabled returns 422, which is a clear enough
error that it is worth testing before writing the loop that makes ten of them.

## provisioning, end to end

1. `client.domains.create(domain="yourdomain.tld", subdomains_enabled=True)`, and keep the returned
   records.
2. publish them, with the wildcard MX, using the zone file if the dns host imports one.
3. poll `GET /domains` until verified. the states above are the vocabulary, not a boolean.
4. `client.inboxes.create(request=CreateInboxRequest(username="[name]", domain="agents.yourdomain.tld"))`.
5. set `HEYPHONY_MAIL_SECRET` and point the webhook at the catcher. their scheme here is a plain shared
   header (`x-agentmail-secret`), which covers less than svix does: the header proves who sent it, not
   that the body is intact, so the lane compares it in constant time and treats the payload as data.

## what is not recorded here

the plan's figures. their docs pages document domains, inboxes and the api; the pricing page did not
load when this was written, so this page does not claim a price. what it does claim, because the owner
established it and it is the line that matters: a custom domain needs the paid plan, and the free tier
gives `@agentmail.to` addresses only.
