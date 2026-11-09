# commands, and which step each one settles

one table, because the most common confusion in this package was not knowing which command does the part you are stuck on.

| command | flow | what it settles | safe to run twice |
| --- | --- | --- | --- |
| `heyphony setup` | setup | prints the whole plan for this host as json | yes, it only reads |
| `heyphony setup areas --area-code 212` | setup (buy) | which area codes have stock, the price per rate plan, and the order command it implies | yes, and it is closed rather than guessed without the anveo keys |
| `heyphony setup select sip` | setup | vendor, then existing or new did, then the plan | yes |
| `heyphony setup provision --provider anveo` | setup (buy) | area stock and price, and a prepared order | yes, dry by default |
| `heyphony provision --purchase` | setup (buy) | the order itself | not written on purpose: it spends money |
| `heyphony hooks <vendor>` | setup | prints the url and the setting, and `--apply` arms it | yes |
| `heyphony connect sip --voipms` | setup | writes the 0600 config and one registration | yes, it rewrites the same keys |
| `heyphony doctor` | setup (proof) | what is configured and what is still designed | yes |
| `heyphony serve --port 8099` | manage | runs the catcher that receives texts and carrier email | it is a server, one at a time |
| `heyphony app` | manage | the launcher on 127.0.0.1:8790; `--json` prints the tabs, counts and people and exits without serving | same |
| `heyphony allow` | manage | who the agent will hear from: shows the policy and what it means, and `allow mode local`, `allow allow +44...`, `allow block-country poland` or `allow check +46...` edit or test it | yes, every edit prints what it changed |
| `heyphony inbox --since 7` | manage | the raw rows, machine shaped, for a script rather than a person | yes |
| `heyphony calls --missed` | manage | the call log out of the client's own sqlite, filtered if you ask | yes |
| `heyphony open messages` | manage | reads the inbox, marks what you looked at | yes, read marks are a sidecar |
| `heyphony open voicemail --play 1` | manage | one recording, and its transcript if one exists | yes |
| `heyphony import --file` | manage | turns a forwarded carrier email into a caught message | yes, deduplicated by id |
| `heyphony send --to +1555... --text "one message"` | manage (out) | one text to one person, gated by `HEYPHONY_SEND=allowed` and `--send` | yes, and it stores what it sent |
| `heyphony voicemail --to +1555... --message "..."` | manage (out) | one call, dialed through your livekit trunk, with the message spoken after the answer | no: `--send` dials a real phone, and `--agent` writes the worker that speaks |
| `heyphony group new --name "dinner" --with ada=+1555...` | manage (out) | a named conversation of two to four people, each message sent one at a time | yes, it refuses a duplicate id by name and time |
| `heyphony group say <id> --text "seven o'clock"` | manage (out) | the same rail, once per member, with each member's own result | no: it sends when `--send` and the gate agree |
| `heyphony group adopt --thread <id> --with +1555...` | manage (in) | takes a carrier thread the carrier already carries and makes it the group, with attribution that is certain | no: it records a thread id |
| `heyphony group reply <id> --text "seven then"` | manage (out) | manage (out) | answers the group after a member writes: the replier gets it in their own thread, everyone else gets a copy | no: same gate and the same `--send` |
| `heyphony group new --name dinner --with ... --number +1555...` | manage (in) | gives the group a did of its own, so replies arrive addressed instead of inferred | no: it records a number you already hold |
| `heyphony group show <id>` | manage (in) | your sends and their replies in one order, with inbound rows matched by membership | reads only |
| `heyphony lookup eval` | lookup | runs the labelled fixture corpus and reports pass, fail, unknown rate and overreach | yes, it only reads |
| `heyphony lookup dana@icloud.com` | lookup | the local part, the domain, and an iMessage verdict of possible, unknown or unlikely | yes, and nothing is sent |
| `heyphony lookup examplemail@gmail.com support` | lookup | the capability matrix: `imessage: true` for an address, false for the services that verify by number | yes, and nothing is sent |
| `heyphony lookup +12125551234 fallback` | lookup | the rails a message would climb, best first, and where the climb stops | yes, and nothing is sent |
| `heyphony lookup alice.42 [--platform signal\|whatsapp]` | lookup | the username form, and the fact that a number is not needed either way | yes, and nobody is messaged |
| `heyphony lookup +1212` | lookup | the country and region from a +1 area code alone, with the subscriber digits never asked for | yes, and nothing is sent |
| `heyphony lookup +447700900123` (`--lookup` also works) | lookup | what the number is: line class, whether it can take a text, and the market's coverage | yes, it reads a plan |
| `heyphony --lookup +1555... support` | lookup | the same line, one verdict per service, with `possible` and `unlikely` instead of a boolean | yes |
| `heyphony --lookup +1555... probes` | lookup | the probes each service would need, and what running one would do to somebody's phone | yes, and nothing is dialed |
| `heyphony get signal` | onramp | prints the recipe for signal, `--run` executes the install steps | yes |
| `heyphony status` | any | one line per lane: open, closed, designed | yes |

one entry is deliberately absent: there is no `heyphony call`, because baresip's socket is chosen and not driven yet. the outbound commands that do exist are all shaped like one person doing one thing: `send` writes to one number, `voicemail` dials one number, and `say` in a group is a loop over that same rail rather than a lane of its own. a command that pretends to place a call it cannot drive would be the most expensive kind of lie in a telephony tool.
