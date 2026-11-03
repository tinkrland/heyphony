"""evalrun: run the labelled fixtures and report what the lookup got right, wrong and unknown.

the honest part first: the fixtures and the tables were written by the same hand, so a pass here proves
the code agrees with the table, not that the table is right about the world. what a fixture run *can*
catch is the class of bug that matters most in a lookup tool, which is **overreach**: claiming a line
type, a country or a text capability that the evidence does not carry. so overreach is counted
separately from a wrong answer, and `unknown` is reported as its own rate rather than folded into the
failures.

the contrast pairs are the design. two numbers from the same market that must not receive the same
answer are the only real test that an answer is derived rather than guessed from a familiar shape.
"""
import json
import pathlib

from src.lookup import classify

CORPUS = pathlib.Path(__file__).with_name("corpus.json")

# fields where a claim beyond the evidence is overreach rather than an honest miss
CLAIMS = ("market", "type", "region", "receive_text")


def cases(path=None):
    data = json.loads(pathlib.Path(path or CORPUS).read_text())
    return data["cases"], data["_note"]


def run(path=None):
    rows = []
    for case in cases(path)[0]:
        got = classify.classify(case["number"])
        expect = case["expect"]
        wrong = [k for k, v in expect.items() if got.get(k) != v]
        overreach = [k for k, v in expect.items()
                     if k in CLAIMS and got.get(k) not in (None, "unknown", v)]
        rows.append({"id": case["id"], "number": case["number"], "pass": not wrong,
                     "wrong": wrong, "overreach": overreach,
                     "got": {k: got.get(k) for k in ("market", "type", "receive_text", "region")},
                     "expected": expect, "why": case.get("why")})
    total = len(rows)
    passed = sum(1 for r in rows if r["pass"])
    unknown = sum(1 for r in rows if r["got"]["type"] == "unknown")
    return {"cases": total, "pass": passed, "fail": total - passed,
            "unknown_rate": round(unknown / total, 3) if total else 0,
            "overreach": [r for r in rows if r["overreach"]],
            "failures": [r for r in rows if not r["pass"]],
            "note": cases(path)[1],
            "how_to_read": ("a pass proves the code agrees with the table. it does not prove the table "
                            "is right, and no rate here should be quoted as accuracy"),
            "rows": rows}
