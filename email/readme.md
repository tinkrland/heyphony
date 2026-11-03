# email

the agent's own mailbox, and the only lane that has to work while the machine is
off. the provider catches the mail, so an idle host still has mail waiting when it wakes. carlyemail
is the one to start with: three inboxes and 1000 emails a month on a domain of your own, free.
agentmail needs a paid plan before it will hold a custom domain, so on its free tier the address is
`@agentmail.to`, which is the shared-reputation shape this lane exists to avoid.

getting the address is the step before this one, and both providers are written up with their dns records, subdomain behaviour and traps in [provisioning](provisioning/readme.md): [carlyemail](provisioning/carlyemail.md) (custom domain on the free tier) and [agentmail](provisioning/agentmail.md) (per-record verification and subdomain reputation).

wired: the front door. two schemes, one of them good: svix (`whsec_` secret,
`webhook-id`/`webhook-timestamp`/`webhook-signature` over `id.timestamp.body`, so
the body is covered and the signature expires), or a plain shared header for a
provider that only offers that. then a sender whitelist, because an invite from a
stranger is not work.

not wired: sending. relay is narrow on purpose and runs through `SMTP_URL` only.

gate: `CARLYEMAIL_SIGNING_SECRET` (svix) or `HEYPHONY_MAIL_SECRET` (plain), plus
`HEYPHONY_FORWARD_WHITELIST` and `SMTP_URL`. unset closes the lane.
