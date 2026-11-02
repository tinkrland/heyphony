"""the task: what the call is for, what to find out, and how the answer comes back.

this is the piece the hosted calling services genuinely did better than a plain dialler, and it is
worth taking seriously: a call with a stated goal, a list of things to find out, and a structured
result is a different object from a call with a script. what is taken from [call-e](https://heycall-e.com)
is the *shape* of that idea, credited here and implemented locally against our own client and our own
reasoning. no request goes to their hosted dialer, and no audio leaves the machine except the call.

the vocabulary below is deliberately borrowed (result_status, call_outcome, the four-state envelope),
because a caller that already reads one calling tool should not have to learn a second dialect to read
this one. the values are produced here, by us, and validated here against the schema we shipped.
"""
import json

RESULT_STATUS = ("pending", "available", "unavailable", "not_applicable")
CALL_OUTCOMES = ("completed", "no_answer", "busy", "declined", None)

# the schema features this lane will honour. an extraction model that is asked for $ref or oneOf will
# happily return something, which is exactly why the refusal happens before the call rather than after.
SUPPORTED = ("type", "properties", "required", "enum", "description", "items", "additionalProperties")
UNSUPPORTED = ("$ref", "oneOf", "anyOf", "allOf", "not", "patternProperties")

JSON_TYPES = {"object": dict, "array": list, "string": str, "number": (int, float),
              "integer": int, "boolean": bool}


def task(goal, must_collect=None, success=None, notes=None, language=None):
    """one call, described before it is placed. `must_collect` is a schema, not prose."""
    return {
        "goal": str(goal or "").strip(),
        "must_collect": must_collect,
        "success": success,
        "notes": notes,
        "language": language,
    }


def clarifications(item, to=None):
    """what is missing before a call is worth placing, in the same needs/flag shape as the rest."""
    missing = []
    if not item.get("goal"):
        missing.append({"needs": "goal", "flag": "--goal",
                        "why": "a call without a goal is a wrong number with extra steps"})
    if not str(to or "").strip():
        missing.append({"needs": "phone", "flag": "--to",
                        "why": "one recipient, e164, and the registration to reach them with"})
    schema = item.get("must_collect")
    if not schema:
        missing.append({"needs": "must_collect", "flag": "--schema",
                        "why": "without a schema the call returns a summary somebody has to read, "
                               "which is the problem this lane exists to remove"})
    else:
        for problem in schema_problems(schema):
            missing.append(problem)
    if not item.get("success"):
        missing.append({"needs": "success", "flag": "--success",
                        "why": "how would either side know the call achieved anything"})
    return missing


def schema_problems(schema):
    """the documented subset, checked before the call rather than after the transcript."""
    problems = []
    text = json.dumps(schema)
    for feature in UNSUPPORTED:
        if f'"{feature}"' in text:
            problems.append({"needs": "schema", "unsupported": feature,
                             "why": "unsupported by the extraction contract, so it would pass and return "
                                    "an empty object instead of failing loudly"})
    if not isinstance(schema, dict) or schema.get("type") != "object":
        problems.append({"needs": "schema", "unsupported": "root",
                         "why": "the result is an object, because a call has fields"})
    return problems


def validate(value, schema, path="$"):
    """a small json-schema validator for exactly the subset a call result needs.

    this runs locally on the extracted answer, which is the whole point: a schema nobody checks is a
    wish. it is not a general validator, and it says so rather than pretending to accept everything.
    """
    problems = []
    if not isinstance(schema, dict):
        return [{"path": path, "problem": "schema", "why": "the schema is an object"}]

    kind = schema.get("type")
    if kind:
        expected = JSON_TYPES.get(kind)
        if expected is None:
            problems.append({"path": path, "problem": "type", "why": f"unsupported type {kind!r}"})
        elif kind == "integer" and isinstance(value, bool):
            problems.append({"path": path, "problem": "type", "why": "a boolean is not an integer"})
        elif not isinstance(value, expected) or (kind != "boolean" and isinstance(value, bool)):
            problems.append({"path": path, "problem": "type",
                             "why": f"expected {kind}, got {type(value).__name__}"})

    if "enum" in schema and value not in (schema.get("enum") or []):
        problems.append({"path": path, "problem": "enum",
                         "why": f"{value!r} is not one of {schema['enum']}"})

    if isinstance(value, dict):
        properties = schema.get("properties") or {}
        for key in schema.get("required") or []:
            if key not in value:
                problems.append({"path": f"{path}.{key}", "problem": "required",
                                 "why": "the call was supposed to answer this"})
        for key, subschema in properties.items():
            if key in value:
                problems.extend(validate(value[key], subschema, f"{path}.{key}"))
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    problems.append({"path": f"{path}.{key}", "problem": "additional",
                                     "why": "the schema is strict, so an invented field is a rejected one"})

    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, entry in enumerate(value):
            problems.extend(validate(entry, schema["items"], f"{path}[{index}]"))
    return problems


def envelope(result=None, schema=None, transcript=None, outcome=None, error=None):
    """the four-state answer, produced here. pending is the caller's word, not ours: we only return
    once the call is over, so this envelope never claims to be waiting for itself."""
    problems = validate(result, schema) if (schema and result is not None) else []
    if error:
        status = "not_applicable"
        error = dict(error) if isinstance(error, dict) else {"code": str(error)}
    elif problems:
        status = "unavailable"
        error = {"code": "result_invalid",
                 "message": "the extracted answer did not survive its own schema",
                 "problems": problems}
    elif result is None:
        status = "unavailable"
        error = {"code": "result_failed", "message": "no result was extracted from the transcript"}
    else:
        status = "available"
        error = None

    return {
        "result_status": status,
        "result": result if status == "available" else None,
        "error": error,
        "call_outcome": outcome if outcome in CALL_OUTCOMES else None,
        "transcript": [dict(turn) for turn in (transcript or []) if isinstance(turn, dict)],
    }


def fields(schema):
    """the fields, with the words that tell a reader what to listen for."""
    rows = []
    for key, subschema in ((schema or {}).get("properties") or {}).items():
        rows.append({"field": key, "type": (subschema or {}).get("type"),
                     "description": (subschema or {}).get("description"),
                     "enum": (subschema or {}).get("enum")})
    return rows


def extract_prompt(item, transcript):
    """the question we ask our own model, built deterministically so it can be read and diffed.

    no vendor, no network: this returns text. what a host does with it is the host's business, and a
    test can check the text without a model anywhere near it.
    """
    lines = ["a phone call has finished. read the transcript and answer only what was asked for.", ""]
    lines.append(f"the goal of the call was: {item.get('goal')}")
    if item.get("notes"):
        lines.append(f"context: {item['notes']}")
    schema = item.get("must_collect") or {}
    if schema.get("properties"):
        lines.append("")
        lines.append("answer these fields, and nothing else:")
        for row in fields(schema):
            detail = f"- {row['field']} ({row['type']})"
            if row.get("enum"):
                detail += f", one of {row['enum']}"
            if row.get("description"):
                detail += f": {row['description']}"
            lines.append(detail)
        lines.append("")
        lines.append("use the string \"unknown\" for anything the call did not establish. never guess, "
                     "and never invent a field that is not listed.")
    lines.append("")
    lines.append("transcript:")
    for turn in transcript or []:
        if isinstance(turn, dict):
            offset = turn.get("offset")
            speaker = turn.get("speaker") or "unknown"
            lines.append(f"[{offset if offset is not None else '?'}] {speaker}: {turn.get('text', '')}")
    lines.append("")
    lines.append("reply with one json object and nothing else.")
    return "\n".join(lines)
