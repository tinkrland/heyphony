"""email: what an address can and cannot say about reaching someone on iMessage.

the same shape as the number lookup, for the same reason. a number lookup can say where a line is and
rarely what answers it; an email lookup can say what kind of address it is and almost never whether the
person behind it has an apple account. so the answer is evidence with its scope, an `unknown` that is a
real result, and a `withheld` map naming what the address cannot carry.

why email at all: iMessage reaches people at an apple account, and an apple account is often an email
address. three of them are apple's own, so `@icloud.com`, `@me.com` and `@mac.com` are apple account
addresses by construction (apple's own support page describes those three as the address forms an icloud
account gets). every other address is a question only the person can answer.

the deliberate limit: no network. mx records and mailbox existence both need dns, and a probe that
messages somebody to see what happens is not a lookup, it is contact. so `exists` and `deliverable` are
withheld rather than guessed, and `probes` lists what a wired probe would do.
"""
import re

# apple's own address forms: an icloud account is issued one of these, so the address IS an apple account
APPLE = {"icloud.com", "me.com", "mac.com"}

# consumer mailbox providers: a personal address at somebody else's mailbox, which says nothing about apple
CONSUMER = {
    "gmail.com", "googlemail.com", "outlook.com", "outlook.jp", "hotmail.com", "hotmail.co.uk",
    "live.com", "msn.com", "yahoo.com", "yahoo.co.uk", "yahoo.co.in", "ymail.com", "aol.com",
    "proton.me", "protonmail.com", "pm.me", "tuta.com", "tutanota.com", "gmx.com", "gmx.net",
    "mail.com", "zoho.com", "fastmail.com", "hey.com", "yandex.com", "yandex.ru", "mail.ru",
    "qq.com", "163.com", "126.com", "sina.com", "naver.com", "daum.net", "web.de", "gmx.de",
    "orange.fr", "free.fr", "laposte.net", "libero.it", "bol.com.br", "uol.com.br",
}

# throwaway domains: the address exists long enough to be written down and not long enough to be a person
DISPOSABLE = {
    "mailinator.com", "guerrillamail.com", "sharklasers.com", "grr.la", "10minutemail.com",
    "tempmail.com", "temp-mail.org", "yopmail.com", "trashmail.com", "dispostable.com",
    "getnada.com", "maildrop.cc", "mytemp.email", "throwawaymail.com", "spam4.me",
}

# a desk rather than a person: nobody's apple account is called support
ROLE = {
    "info", "support", "sales", "admin", "administrator", "hello", "contact", "help", "billing",
    "accounts", "accounting", "orders", "shop", "team", "press", "media", "jobs", "careers",
    "hr", "legal", "privacy", "security", "abuse", "postmaster", "webmaster", "hostmaster",
    "noreply", "no-reply", "donotreply", "do-not-reply", "notifications", "newsletter", "marketing",
}

LABEL = r"(?!-)[a-z0-9-]{1,63}(?<!-)"
DOMAIN_RE = re.compile(r"^" + LABEL + r"(?:\." + LABEL + r")+$")
LOCAL_RE = re.compile(r"^[a-z0-9!#$%&'*+/=?^_`{|}~.-]{1,64}$")

NOTES = {
    "no_network": "no request leaves the machine, so dns and mailbox checks are withheld rather than "
                  "attempted",
    "apple_forms": "apple issues an icloud account one of @icloud.com, @me.com or @mac.com, so those "
                   "three are apple account addresses by construction",
    "everything_else": "an apple account can be any email address, so a non-apple address is a question "
                       "for the person rather than a fact about the string",
}


def classes(address):
    """the local part and the domain, each answered separately, because they mean different things."""
    got = address.strip().lower()
    if got.count("@") != 1:
        return {"valid": False, "why": "an address has exactly one @, and this has "
                                       f"{got.count('@')}"}
    local, domain = got.split("@")
    if not local or not domain:
        return {"valid": False, "why": "one side of the @ is empty"}
    if not DOMAIN_RE.match(domain):
        return {"valid": False, "why": f"`{domain}` is not a domain: labels of letters, digits and "
                                       f"hyphens, at least one dot, no leading or trailing hyphen"}
    if not LOCAL_RE.match(local):
        return {"valid": False, "why": f"`{local}` carries a character an address cannot: spaces, "
                                       f"quotes and the bracket characters are not carried here"}
    tld = domain.rsplit(".", 1)[-1]
    if not tld.isalpha() or len(tld) < 2:
        return {"valid": False, "why": f"`{tld}` is not a top level domain"}

    tagged = "+" in local
    stem = local.split("+", 1)[0]
    local_class = "role address" if stem in ROLE else ("personal mailbox" if not tagged
                                                      else "personal mailbox with a tag")
    if domain in APPLE:
        domain_class, host = "apple account address", "apple"
    elif domain in DISPOSABLE:
        domain_class, host = "disposable domain", "disposable"
    elif domain in CONSUMER:
        domain_class, host = "consumer mailbox", "consumer"
    else:
        domain_class, host = "custom domain", "custom"
    return {"valid": True, "local": local, "domain": domain, "stem": stem, "tagged": tagged,
            "local_class": local_class, "domain_class": domain_class, "host": host, "tld": tld}


def _imessage(found):
    """the verdict, and the reason it is that verdict rather than a probability."""
    host, local_class = found["host"], found["local_class"]
    if host == "apple":
        return "possible", ("this address is an apple account address by construction, so it can hold "
                            "an apple account. whether that account has iMessage on, and whether the "
                            "person reads it, is still theirs to decide")
    if host == "disposable":
        return "unlikely", ("a throwaway domain is not where somebody's apple account lives, and the "
                            "address will be gone before a reply arrives")
    if local_class == "role address":
        return "unlikely", ("a shared desk is not an apple account. mail to it is answered by whoever "
                            "is on shift rather than by a person with an imessage setting")
    if host == "consumer":
        return "unknown", ("a consumer mailbox can be an apple account identifier, and most of them "
                           "are not used as one. the string cannot separate the two")
    return "unknown", ("an apple account can be any address, so a work address is exactly as likely "
                       "and exactly as unknowable as any other. only the person can say")


def lookup(address):
    """what the address says, what it cannot say, and nothing beyond that."""
    raw = str(address or "").strip()
    found = classes(raw)
    answer = {"input": raw, "kind": "email", "valid": bool(found["valid"]), "verified": False,
              "notes": NOTES, "privacy": {"derived_from": "the address string, read locally",
                                          "network": "no request leaves the machine",
                                          "retention": "nothing is stored"}}
    if not found["valid"]:
        answer.update({"imessage": "unknown", "local_class": None, "domain_class": None,
                       "evidence": [], "withheld": {"everything": found["why"]},
                       "why": f"not an address this reader accepts: {found['why']}"})
        return answer

    verdict, why = _imessage(found)
    answer.update({"local_class": found["local_class"], "domain_class": found["domain_class"],
                   "domain": found["domain"], "imessage": verdict, "why": why,
                   "withheld": {
                       "exists": "whether the mailbox exists needs dns and a relay. no request leaves "
                                 "the machine, so this is unanswered rather than guessed",
                       "deliverable": "same as existence: a check would be a probe, and this is a "
                                      "lookup",
                       "reachable_by_imessage": "an apple account is a person's to disclose. the "
                                                "address can narrow it, never confirm it"}})
    if found["host"] == "apple":
        answer["withheld"].pop("reachable_by_imessage")
        answer["withheld"]["imessage_enabled"] = ("this is an apple account address, but whether that "
                                                  "account turned iMessage on is a setting, not a "
                                                  "property of the address")

    evidence = [{"strength": "syntax", "source": "the address string",
                 "why": "the shape of an address is checkable locally and offline"}]
    if found["host"] == "apple":
        evidence.append({"strength": "issuer", "source": "apple support: the three icloud address forms",
                         "why": NOTES["apple_forms"]})
    elif found["host"] == "consumer":
        evidence.append({"strength": "provider", "source": "a carried list of consumer mailbox domains",
                         "why": "a personal mailbox at somebody else's provider, which says nothing "
                                "about apple either way"})
    elif found["host"] == "disposable":
        evidence.append({"strength": "provider", "source": "a carried list of throwaway domains",
                         "why": "the domain exists to be discarded"})
    else:
        evidence.append({"strength": "provider", "source": "not one of the carried providers",
                         "why": "a domain somebody runs themselves, most often a work or school "
                                "domain"})
    evidence.append({"strength": "unseeded", "source": "no probe is wired",
                     "why": "existence, deliverability and apple account status all need a request, and "
                            "a request to see if somebody answers is contact rather than a lookup"})
    answer["evidence"] = evidence
    answer["probes"] = [{"name": "dns-mx", "would_answer": "deliverable, and whether the domain "
                                                           "accepts mail at all",
                         "wired": False},
                        {"name": "smtp-rcpt", "would_answer": "existence, at the cost of a connect the "
                                                              "domain owner can see", "wired": False}]
    return answer
