# carlyemail: a domain of your own on the free tier

read from `docs.carlyemail.com` in november 2026, including `guides/custom-domains`. the api is
`https://api.carlyemail.com/v0`, the cli is `npx carlyemail`, and the free plan is three inboxes and
1,000 emails a month with no card, which is the fact that makes this the first provider to try.

## what you get

- **an address immediately.** `carly.inboxes.create({"username": "hello"})` returns a working inbox,
  `hello@carlyemail.com` by default, with no dashboard and no waiting.
- **your own domain, on the free tier.** `hello@yourcompany.com` instead, and the sending reputation
  is yours rather than shared with every other tenant on their domain.
- **threads, not adjacent messages.** replies land in the conversation, and `messages.reply` answers
  inside their thread, which is the difference between a mailbox and a queue.
- **events that wake a runtime.** a signed webhook or a websocket the second mail arrives.
- **an mcp server**, for an agent runtime that would rather hold tools than an sdk.

## the custom domain, exactly as their page lays it out

three routes: by hand through the dns provider, in code with two calls and a status field, or by an
agent that adds the domain, waits, and says which record is wrong.

```bash
npx carlyemail domain mail.yourcompany.com            # returns the records to publish
npx carlyemail domain mail.yourcompany.com --zone > carlyemail.zone
npx carlyemail domain mail.yourcompany.com --check    # per-record VALID or MISSING
npx carlyemail domain mail.yourcompany.com --subdomains
```

in code it is `domains.create`, `domains.verify`, and `inboxes.create` with `domain` set:

```python
domain = carly.domains.create({"domain": "mail.yourcompany.com"})
checked = carly.domains.verify(domain["domain_id"])   # PENDING until every record resolves
carly.inboxes.create({"username": "hello", "domain": "mail.yourcompany.com"})
```

the five or six records, and what each one is for:

| type | name | why |
| --- | --- | --- |
| cname x3 | `<token>._domainkey.mail.yourcompany.com` | signs the mail so it is not treated as forged |
| txt | `bounce.mail.yourcompany.com` | says they are allowed to send as you |
| mx | `bounce.mail.yourcompany.com` | where bounces go |
| txt | `_dmarc.mail.yourcompany.com` | what receivers do with mail that fails the checks |
| mx | `mail.yourcompany.com` | where mail to you is delivered |

**leave the last one out if you only want to send.** that is the sentence that makes this usable beside
an existing mailbox: publish four records, and mail addressed to the domain keeps going wherever the
existing MX already points.

## the traps their page names, kept because they are the ones that cost an evening

- **the name field is usually relative.** a name of `bounce.mail.yourcompany.com` becomes
  `bounce.mail.yourcompany.com.yourcompany.com` if the dns host appends the zone. check what it
  resolves to.
- **dmarc inheritance.** a subdomain inherits a parent's dmarc record but the check looks for the exact
  name, so publish it on the subdomain too. two dmarc records at different levels do not conflict.
- **two mx records doing different jobs.** the bounce MX and the domain MX are not interchangeable,
  and swapping them is the most common way a verified domain still does not receive.
- **verification is reported per record, and a failed lookup is MISSING rather than VALID.** a false
  missing makes you check a record that was fine; a false valid hides the one that is breaking mail.

## subdomains

`subdomains_enabled` adds one wildcard MX on `*.mail.yourcompany.com` plus a ses receipt condition, and
then `agent@customer.mail.yourcompany.com` works without registering the child. turning the setting off
is refused while child-domain inboxes exist, which is the right call: it protects addresses that are
already in somebody's address book.

## what to do with the key

scope it. their docs suggest a key with `domain_create` and `domain_read` and nothing else for the
provisioning job, because adding a domain is not a reason to also be able to read the mail. then set
`CARLYEMAIL_SIGNING_SECRET` from the webhook's svix signing secret, and the lane above verifies
`id.timestamp.body` in constant time with a freshness window.
