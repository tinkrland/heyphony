import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from brain import adapters, compat, turn  # noqa: E402


def readme():
    """the branch's page, not the number's: the root readme is what `mcp` argues, and this branch
    adds a way to use it rather than replacing the argument."""
    return (ROOT / "brain" / "readme.md").read_text()


class TestThePageAndTheDataAgree(unittest.TestCase):
    def test_the_page_is_this_branch(self):
        text = readme()
        self.assertTrue(text.startswith("# brain"))
        self.assertNotIn("\u2014", text, "no em dashes")

    def test_every_adapter_is_named_on_the_page(self):
        text = readme().lower()
        for name in adapters.known():
            self.assertIn(name, text, f"{name} is an adapter but the page does not name it")

    def test_every_adapter_row_is_complete(self):
        for name, row in adapters.ADAPTERS.items():
            for key in ("name", "what", "kind", "auth", "evidence", "needs"):
                self.assertIn(key, row, f"{name} has no {key}")
            self.assertEqual(row["name"], name)
            self.assertIn(row["kind"], ("cli", "http"))

    def test_an_http_row_names_its_endpoint_and_a_cli_row_names_its_command(self):
        for name, row in adapters.ADAPTERS.items():
            if row["kind"] == "http":
                for key in ("base", "path", "model_env", "default_base", "default_model"):
                    self.assertIn(key, row, f"{name} is http and has no {key}")
            else:
                self.assertTrue(row.get("argv") or row["binary"].isupper(),
                                f"{name} is a cli adapter with neither argv nor an env binary")

    def test_the_refusals_are_on_the_page(self):
        text = readme().lower()
        for line in adapters.REFUSED:
            head = line.split(":")[0].split(",")[0]
            self.assertIn(head.split()[0], text, f"the page does not carry the refusal {head!r}")


class TestTheCommandIsBuiltNotGuessed(unittest.TestCase):
    def test_a_prompt_reaches_claude_on_argv(self):
        argv, stdin = adapters.command("claude", "hello there")
        self.assertEqual(argv, ["claude", "-p", "hello there"])
        self.assertIsNone(stdin)

    def test_a_custom_command_keeps_its_quotes(self):
        env = {"HEYPHONY_BRAIN_CMD": 'python3 -c "print(1)"'}
        argv, stdin = adapters.command("shell", "the prompt", env)
        self.assertEqual(argv, ["python3", "-c", "print(1)"])
        self.assertEqual(stdin, "the prompt")

    def test_no_secret_is_ever_placed_on_a_command_line(self):
        env = {"OPENAI_API_KEY": "sk-live-very-secret", "HEYPHONY_BRAIN_CMD": "cat",
               "PATH": "/usr/bin:/bin"}
        for name in adapters.known():
            if adapters.ADAPTERS[name]["kind"] != "cli":
                continue
            argv, stdin = adapters.command(name, "a prompt", env)
            joined = " ".join(argv) + " " + (stdin or "")
            self.assertNotIn("sk-live-very-secret", joined, f"{name} leaked a key")

    def test_redact_hides_a_key_that_was_pasted_into_a_command(self):
        env = {"OPENAI_API_KEY": "sk-live-very-secret"}
        clean = adapters.redact(["--key", "sk-live-very-secret"], env)
        self.assertEqual(clean, ["--key", "<redacted>"])

    def test_an_uninstalled_brain_says_what_is_missing(self):
        self.assertIn("claude", adapters.missing("claude", {"PATH": "/nonexistent"}))
        self.assertIn("OPENAI_API_KEY", adapters.missing("openai", {}))


class Stub(BaseHTTPRequestHandler):
    seen = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        Stub.seen = {"path": self.path, "auth": self.headers.get("Authorization"),
                     "body": json.loads(body)}
        if "unauthorized" in self.path:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"error":"no"}')
            return
        if "garbage" in self.path:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"not json at all")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"choices": [{"message": {"content": "hello back"}}]}).encode())

    def log_message(self, *args):
        pass


class TestTheCompatibleEndpoint(unittest.TestCase):
    """the http adapter against a local stub, so the shape is proven without a network or a bill."""

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Stub)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def env(self, base="/v1", key="sk-test"):
        env = {"OPENAI_BASE_URL": f"http://127.0.0.1:{self.port}{base}",
               "HEYPHONY_BRAIN_MODEL": "a-model"}
        if key:
            env["OPENAI_API_KEY"] = key
        return env

    def prompt(self):
        return {"system": "sys", "user": "the message"}

    def test_the_request_lands_on_the_completions_path_with_a_bearer(self):
        ok, text = compat.ask(adapters.get("openai"), self.prompt(), self.env())
        self.assertTrue(ok, text)
        self.assertEqual(text, "hello back")
        self.assertEqual(Stub.seen["path"], "/v1/chat/completions")
        self.assertEqual(Stub.seen["auth"], "Bearer sk-test")
        self.assertEqual(Stub.seen["body"]["model"], "a-model")
        self.assertEqual([m["role"] for m in Stub.seen["body"]["messages"]], ["system", "user"])

    def test_a_trailing_slash_in_the_base_does_not_double_the_path(self):
        odd = self.env(base="/v1/")
        self.assertTrue(compat.url(adapters.get("openai"), odd).endswith("/v1/chat/completions"))

    def test_no_model_env_falls_back_to_the_row_default(self):
        env = self.env()
        env.pop("HEYPHONY_BRAIN_MODEL")
        self.assertEqual(compat.model(adapters.get("openai"), env),
                         adapters.get("openai")["default_model"])

    def test_a_refused_status_is_an_answer_about_the_endpoint(self):
        ok, why = compat.ask(adapters.get("openai"), self.prompt(), self.env(base="/v1/unauthorized"))
        self.assertFalse(ok)
        self.assertIn("401", why)

    def test_a_reply_that_is_not_json_says_so(self):
        ok, why = compat.ask(adapters.get("openai"), self.prompt(), self.env(base="/v1/garbage"))
        self.assertFalse(ok)
        self.assertIn("not json", why)

    def test_a_missing_key_stops_before_the_request(self):
        ok, why = compat.ask(adapters.get("openai"), self.prompt(), self.env(key=None))
        self.assertFalse(ok)
        self.assertIn("OPENAI_API_KEY", why)


class TestOneTurnMakesTheDecisions(unittest.TestCase):
    ROW = {"id": "sms:1", "channel": "sms", "sender": "+15550000002", "at": 1794900000,
           "body": "are you free at 6?", "raw": {"secret": "carrier payload"}}

    def env(self, **over):
        base = {"HEYPHONY_BRAIN_CMD": "the-brain", "HEYPHONY_SEND": ""}
        base.update(over)
        return base

    def test_the_prompt_carries_the_message_and_not_the_carrier_payload(self):
        prompt = turn.prompt_for(self.ROW)
        self.assertIn("are you free at 6?", prompt["user"])
        self.assertIn("+15550000002", prompt["user"])
        self.assertNotIn("carrier payload", prompt["user"])
        self.assertIn("DROP", prompt["system"])

    def test_drop_is_honoured(self):
        self.assertEqual(turn.decide("DROP", {}, "+1555")["action"], "drop")
        self.assertEqual(turn.decide("drop.", {}, "+1555")["action"], "drop")
        self.assertEqual(turn.decide("", {}, "+1555")["action"], "drop")

    def test_a_shut_gate_drafts_and_the_draft_has_no_send_flag(self):
        said = turn.decide("yes, six works", {"HEYPHONY_SEND": ""}, "+1555")
        self.assertEqual(said["action"], "draft")
        self.assertNotIn("argv", said)

    def test_an_open_gate_sends_through_the_numbers_own_rail(self):
        said = turn.decide("yes, six works", {"HEYPHONY_SEND": "allowed"}, "+1555")
        self.assertEqual(said["action"], "send")
        self.assertIn("--send", said["argv"])
        self.assertEqual(said["argv"][:1], ["send"])

    def test_a_reply_with_nowhere_to_go_is_dropped_rather_than_broadcast(self):
        said = turn.decide("yes", {"HEYPHONY_SEND": "allowed"}, None)
        self.assertEqual(said["action"], "drop")
        self.assertIn("--to", said["why"])

    def test_a_turn_drafts_when_the_gate_is_shut(self):
        said = turn.one_turn("shell", self.ROW, self.env(), "+1555",
                             runner=lambda argv, stdin: (True, "six is fine"))
        self.assertTrue(said["ok"])
        self.assertEqual(said["decision"]["action"], "draft")
        self.assertFalse(said["sent"])

    def test_a_turn_sends_when_the_gate_is_open_and_says_it_sent(self):
        said = turn.one_turn("shell", self.ROW, self.env(HEYPHONY_SEND="allowed"), "+1555",
                             runner=lambda argv, stdin: (True, "six is fine"))
        self.assertTrue(said["sent"])
        self.assertEqual(said["decision"]["action"], "send")

    def test_a_brain_that_fails_sends_nothing(self):
        said = turn.one_turn("shell", self.ROW, self.env(HEYPHONY_SEND="allowed"), "+1555",
                             runner=lambda argv, stdin: (False, "boom"))
        self.assertFalse(said["ok"])
        self.assertFalse(said["sent"])
        self.assertEqual(said["why"], "boom")

    def test_an_unready_brain_spends_nothing(self):
        called = []
        said = turn.one_turn("openai", self.ROW, {}, "+1555",
                             runner=lambda *a: called.append(a) or (True, "x"))
        self.assertFalse(said["ok"])
        self.assertIn("OPENAI_API_KEY", said["missing"])
        self.assertEqual(called, [])


class TestTheCliAnswersBeforeItSpends(unittest.TestCase):
    def run_brain(self, *args, env=None):
        merged = dict(os.environ)
        merged.pop("OPENAI_API_KEY", None)
        merged.update(env or {})
        merged["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run([str(ROOT / "bin" / "brain"), *args], capture_output=True,
                              text=True, timeout=120, env=merged)

    def envelope(self, tmp):
        path = pathlib.Path(tmp) / "envelope.json"
        path.write_text(json.dumps(TestOneTurnMakesTheDecisions.ROW))
        return str(path)

    def test_adapters_lists_every_row_without_spending(self):
        done = self.run_brain("adapters")
        self.assertEqual(done.returncode, 0, done.stderr)
        said = json.loads(done.stdout)
        self.assertEqual(sorted(said["adapters"]), adapters.known())

    def test_refused_prints_the_refusals(self):
        said = json.loads(self.run_brain("refused").stdout)
        self.assertEqual(len(said["refused"]), len(adapters.REFUSED))

    def test_plan_shows_the_request_and_the_gate_decision_and_spends_nothing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            said = json.loads(self.run_brain("plan", "--brain", "openai",
                                             "--file", self.envelope(tmp), "--to", "+1555",
                                             env={"OPENAI_API_KEY": "sk-test"}).stdout)
        self.assertEqual(said["request"]["model"], adapters.get("openai")["default_model"])
        self.assertIn("/chat/completions", said["request"]["url"])
        self.assertEqual(said["decision_now"]["action"], "draft")

    def test_a_brain_that_is_not_installed_says_so_before_a_turn(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            done = self.run_brain("run", "--brain", "claude", "--file", self.envelope(tmp),
                                  "--to", "+1555",
                                  env={"PATH": "/nonexistent", "HEYPHONY_PYTHON": sys.executable})
        said = json.loads(done.stdout)
        self.assertFalse(said["ok"])
        self.assertIn("claude", said["missing"])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    failed = len(result.failures) + len(result.errors)
    print(f"brain selftest: {result.testsRun - failed}/{result.testsRun} pass")
    sys.exit(1 if failed else 0)
