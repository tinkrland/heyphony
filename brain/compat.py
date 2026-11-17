"""one http shape, over urllib, because this package installs with nothing beside it.

the compatible-endpoint brain is the same request every tool makes: a model name, one system line,
one user line, and a text back. the base url is configuration rather than a constant, so a local
server, a proxy and the vendor are the same code path, and the key is read from the environment at
the moment of the call so it is never written anywhere.
"""
import json
import urllib.error
import urllib.request

TIMEOUT = 60


def base(row, env):
    return (env.get(row["base"]) or row["default_base"]).rstrip("/")


def url(row, env):
    return base(row, env) + row["path"]


def model(row, env):
    return env.get(row["model_env"]) or row["default_model"]


def payload(prompt, row, env):
    """the smallest request the shape allows: no tools, no stream, one answer."""
    return {
        "model": model(row, env),
        "messages": [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"]},
        ],
        "stream": False,
    }


def text_of(reply):
    """the answer, or a sentence saying which part of the shape was not there."""
    if not isinstance(reply, dict):
        return None, "the reply was not a json object"
    choices = reply.get("choices")
    if not isinstance(choices, list) or not choices:
        return None, "the reply has no choices"
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        return None, "the first choice carries no message content"
    return content.strip(), None


def ask(row, prompt, env, opener=None, timeout=TIMEOUT):
    """one request. returns (ok, answer or why). a refused status is an answer about the endpoint,
    not an exception to swallow, so it comes back as the why."""
    import os
    env = env if env is not None else os.environ
    key = env.get("OPENAI_API_KEY")
    if not key:
        return False, "OPENAI_API_KEY is unset, and an endpoint that needs no key is still asked for one"
    body = json.dumps(payload(prompt, row, env)).encode()
    request = urllib.request.Request(url(row, env), data=body, method="POST",
                                    headers={"Content-Type": "application/json",
                                             "Authorization": f"Bearer {key}"})
    open_ = opener or urllib.request.urlopen
    try:
        with open_(request, timeout=timeout) as response:
            raw = response.read().decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf8", "replace")[:300]
        return False, f"the endpoint answered {exc.code}: {detail}"
    except urllib.error.URLError as exc:
        return False, f"the endpoint could not be reached: {exc.reason}"
    try:
        answer = json.loads(raw)
    except ValueError:
        return False, f"the endpoint answered something that is not json: {raw[:120]}"
    text, why = text_of(answer)
    return (True, text) if text else (False, why)


def plan(row, prompt, env):
    """what would be spent, printed before it is spent."""
    key = bool((env or {}).get("OPENAI_API_KEY"))
    return {"url": url(row, env), "model": model(row, env), "method": "POST",
            "auth": "bearer from OPENAI_API_KEY" if key else "OPENAI_API_KEY is unset",
            "bytes": len(json.dumps(payload(prompt, row, env))),
            "spends": "one model call per arrival, and nothing else"}
