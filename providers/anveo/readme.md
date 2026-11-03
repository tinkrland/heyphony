# anveo

the one vendor in this list with a whole chain a program can walk, from ordering a number to arming the hook that catches its texts.

## why it is the most implacable of the ten

most providers document an api for numbers and expect you to arm the sms hook in a portal, by hand, once. anveo documents that call too, so the number is a transaction this repo can finish on its own: `DID.ORDER` buys one, `DID.UPDATE` sets `SMS_URL` on it, `DID.LIST` shows what you hold. that is a ten minute job that becomes one command.

the api is `api/v3.asp` with `?userkey=KEY&action=ACTION&param[NAME]=VALUE`, and every request carries a signature that is `hmac_sha1(key=secure phrase, message=account email)` in hex. their published example vector is pinned in the suite, which is the only reason to trust the signing rather than hope. environment: `ANVEO_USERKEY`, `ANVEO_EMAIL`, `ANVEO_SECURE_PHRASE`.

## the number

- **about a dollar a month**, sms on the numbers they issue in the united states, canada and the united kingdom.
- geographic, national, tollfree and mobile did types, and `heyphony setup areas --area-code 212` walks the stock instead of guessing what is available.
- **`--test` exists**, which is unusual and worth using: `DID.ORDER` takes `TEST=TRUE`, so the ordering path can be exercised before it spends money.

## how texts arrive

a url forward with placeholder tokens: `$[from]$`, `$[to]$`, `$[message]$`. it is a `GET` with the values in the query string, which is why the catcher handles query strings at all and not only `POST` bodies.

`heyphony hooks anveo --apply --did +1...` runs `DID.UPDATE` with the `SMS_URL` field set to this host's `/sms/anveo` url, so arming the hook is a call and not a portal visit.

## outbound

**gateway not wired.** anveo documents an sms http gateway and keeps the parameter names inside their api portal, behind an account. guessing them is the thing this repo will not do to a page that ends up in front of a real person's phone. `heyphony send --paths` says exactly this, and the fix is small: paste the gateway call from the account page and the row becomes a builder.

## what is still unverified

nobody has paid for an anveo number inside this repo, so the ordering chain has never spent money and no text has ever arrived on a page that claims it can. what *is* proven is the signature, against their published vector.

## setup sketch

1. put `ANVEO_USERKEY`, `ANVEO_EMAIL` and `ANVEO_SECURE_PHRASE` in the environment
2. `heyphony setup areas --area-code 212` to see stock and rates, then `heyphony setup provision --area-code 212 --test` to walk the order without spending
3. `heyphony setup provision --area-code 212 --sms-url auto --apply` when you mean it
4. `heyphony hooks anveo --did +1... --apply` if the number predates this repo
5. `heyphony status`, then text the number and watch it land in `heyphony inbox`
