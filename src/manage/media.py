"""media: the picture that arrives with a text, which is a url and a download and nothing else.

a carrier never puts pixels in a webhook. an mms lands as a text plus one or more urls on the
carrier's own host, and those urls behave like any other file on somebody else's server: they can
expire in days, they can need the account's credentials, and they can be any size the sender felt
like sending. so "the agent can see the screenshot" is three separate facts, and this module only
claims the middle one:

    1. the url was kept            routes.media_of, in the envelope as `media`
    2. something fetched the file  here: one url, a byte cap, a type that decides the suffix
    3. it is what the sender meant not claimed. a file of the right type is not a correct image

the refusals are the shape of the thing, so they are named rather than implied:

    fetch-the-whole-internet   no scheme but http and https, because a webhook is a stranger's input
    a-picture-of-any-size      a byte cap, streamed, so a carrier url cannot fill the disk
    read-as-an-image-what-is-not  the content type picks the suffix. the bytes are never guessed at,
                               because a mislabelled download is a file that lies about itself

what this does not do, stated because the gap is invisible otherwise: it does not authenticate to a
carrier, so a url that needs the account's login comes back as a 401 and is reported as one.
"""
import os
import urllib.error
import urllib.request

MAX_BYTES = 8 * 1024 * 1024

# the types a carrier actually serves for a picture or a voice note, mapped to the suffix it earns
SUFFIX = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/amr": ".amr",
}

ALLOWED_SCHEMES = ("http", "https")


def name_for(message_id, index, content_type):
    """a file name that says which message it belongs to, so a directory of them stays readable."""
    suffix = SUFFIX.get((content_type or "").split(";")[0].strip().lower(), ".bin")
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in str(message_id or "message"))[:60]
    return f"{safe}-{index}{suffix}"


def fetch(url, into, message_id=None, index=0, max_bytes=MAX_BYTES, timeout=20, opener=None):
    """one url, into a directory, with a cap. returns one shape whatever happened."""
    out = {"ok": False, "url": url, "path": None, "bytes": 0, "content_type": None,
           "max_bytes": max_bytes}
    scheme = (url or "").split(":", 1)[0].lower()
    if scheme not in ALLOWED_SCHEMES:
        out["why"] = "fetch-the-whole-internet: only http and https, because this url came in a webhook"
        return out
    opener = opener or urllib.request
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "heyphony/media"})
        with opener.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type") or ""
            if (content_type.split(";")[0].strip().lower()) not in SUFFIX:
                out["content_type"] = content_type
                out["why"] = (f"read-as-an-image-what-is-not: {content_type or 'no type'} is not a "
                              "picture or a voice note this package will name")
                return out
            target = os.path.join(str(into), name_for(message_id, index, content_type))
            total, chunk = 0, True
            os.makedirs(str(into), exist_ok=True)
            with open(target, "wb") as handle:
                while chunk:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        handle.close()
                        os.unlink(target)
                        out["bytes"] = total
                        out["why"] = (f"a-picture-of-any-size: past the {max_bytes} byte cap, so "
                                      "nothing was kept")
                        return out
                    handle.write(chunk)
            out.update({"ok": True, "path": target, "bytes": total, "content_type": content_type})
            return out
    except urllib.error.HTTPError as error:
        out["why"] = (f"the carrier answered {error.code}. these urls usually need the account's own "
                      "login, which this fetch does not send")
        return out
    except Exception as error:  # a stranger's server, so anything at all is possible
        out["why"] = f"{type(error).__name__}: {error}"
        return out


def fetch_all(entry, into, max_bytes=MAX_BYTES, timeout=20, opener=None):
    """every url on one message. a message with four pictures reports four results, not one."""
    urls = entry.get("media") or []
    results = [fetch(url, into, entry.get("id"), index, max_bytes, timeout, opener)
               for index, url in enumerate(urls)]
    return {"id": entry.get("id"), "sender": entry.get("sender"), "results": results,
            "kept": [r["path"] for r in results if r["ok"]],
            "failed": [r["url"] for r in results if not r["ok"]],
            "means": ("a kept file is proof the url was readable at this moment, and nothing about "
                      "what the picture shows")}


def plan():
    """the answer to 'can the agent see the screenshot', as data."""
    return {
        "shipped": True,
        "what": "an inbound message keeps its media urls, and fetch downloads one under a byte cap",
        "envelope": "routes.normalize sets `media` from MEDIA_KEYS; catcher keeps it without a provider",
        "cap_bytes": MAX_BYTES,
        "types": dict(SUFFIX),
        "refused": ["fetch-the-whole-internet", "a-picture-of-any-size",
                    "read-as-an-image-what-is-not"],
        "not_included": [
            "carrier authentication: a url behind the account's login answers 401 and is reported"
            ", which is why the first honest run needs a real carrier",
            "reading the picture: fetching a jpeg is not describing it. that is the caller's job",
            "keeping the url alive: carrier media urls expire, so fetch at read time or not at all",
        ],
    }
