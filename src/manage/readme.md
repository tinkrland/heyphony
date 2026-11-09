# manage: the number answering

setup ends. this folder is everything after, and it is where the agent actually lives: what arrived, who it was from, what happened when nobody answered, and what a reply would be if a send rail existed.

```mermaid
flowchart TD
    M["manage"] --> Q{"is the host up"}
    Q -- "up" --> A["catcher on :8099<br/>texts posted in as they arrive"]
    Q -- "up" --> B["host client registered<br/>calls ring"]
    Q -- "down" --> C["vendor holds it<br/>sms to email, voicemail to email"]
    A --> IN["inbox.py<br/>jsonl, one row per message, deduplicated by provider id"]
    B --> CALLS["call log read from the client's sqlite"]
    C --> MAIL["mailparse.py<br/>the forwarded carrier email becomes a row"]
    MAIL --> IN
    CALLS --> VIEWS["views.py"]
    IN --> VIEWS
    VIEWS --> R1["messages"]
    VIEWS --> R2["voicemail"]
    VIEWS --> R3["missed calls"]
    R1 --> GUI["gui.py: one thread per person"]
    R2 --> GUI
    R3 --> GUI
    GUI --> D["a draft"]
```

## the two states, as folders

`turnedon/` and `turnedoff/` are not modules, they are the two routing worlds, and each has its own page because the difference is not a setting. when the host is up, texts are posted to a url this host is serving and calls ring a client this host is running. when it is down, a vendor with carrier side forwarding emails the text and the voicemail, and a vendor without it holds nothing, so the message is simply gone. the per vendor table is in `turnedoff/readme.md` and the data behind it is `../providers.py`.

## who gets in, before anything is written down

`allow.py` is the door. the catcher normalizes a message, asks `allow.decide(sender)`, and stores it or does not, so nothing downstream ever sees a refused text and nothing downstream has to remember to filter. the policy file is read again for every message, because a security setting that needs a restart to take effect is a setting that is wrong for the length of the restart.

a refusal answers `200` with `stored: false` and the reason, not a `403`: a carrier that sees an error retries, and a retry storm of refused messages is worse than the refusal. the tally lives in `refused.jsonl` with the reason, the region and a shortened number, and never the body.

## the inbox, and what "unread" means

`inbox/` has one page per kind of thing that arrives: texts, voicemail, missed calls. storage is a jsonl file, deduplicated by the provider's own id, because a retried webhook is not a second text. read state is a sidecar file next to it, because a provider webhook never says whether anyone looked, and pretending a delivery implies reading makes the question "is this new" unanswerable.

## and what leaves

`outgoing/` is short and honest: a draft is kept, nothing is sent. when a send rail is wired it will be sms on this number, paid per message, and not imessage, which lives in the umbrella because it is a different rail with a different free tier.
