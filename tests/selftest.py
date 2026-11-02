"""heyphony selftests: stdlib only. run: python3 tests/selftest.py

two kinds of test live here and they protect different things. the first kind pins behaviour,
using fixtures built from the schemas the code actually reads. the second kind pins prose: the
readme, the npm page and the agent page all make claims, and a claim that drifts from the code is
the specific failure mode of a package that has to be trusted with a phone number.
"""
import argparse
import contextlib
import io
import json
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from heyphony.src.runner import cli as telephony_cli
from heyphony.src.manage import catcher as phone_catcher
from heyphony.src.onramp import flow as getters
from heyphony.src.manage import inbox
from heyphony.src import providers
from heyphony.src.setup import flow as setup_flow
from heyphony.src.linphone import sip
from heyphony.src.linphone import sip as linphone


def call_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute("create table call_history (id integer primary key, caller text, callee text,"
                 " direction integer, duration integer, start_time text, connected_time text,"
                 " status integer, videoEnabled integer, quality real, call_id text, refkey text)")
    conn.executemany("insert into call_history (caller, callee, direction, duration, start_time,"
                     " connected_time, status, call_id) values (?,?,?,?,?,?,?,?)", rows)
    conn.commit(); conn.close()


def message_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute("create table history (id integer primary key, localContact text, remoteContact text,"
                 " direction integer, message text, time integer, read integer, status integer,"
                 " url text, utc text, appdata text, content text, messageId text,"
                 " content_type text, is_secured integer)")
    conn.executemany("insert into history (localContact, remoteContact, direction, message, time, read)"
                     " values (?,?,?,?,?,?)", rows)
    conn.commit(); conn.close()


class TestTheShimRuns(unittest.TestCase):
    """a clone is supposed to work with one command. if the shim is wrong, every page above is fiction."""

    shim = ROOT / "bin" / "heyphony"

    def test_the_shim_answers_with_json_and_nothing_else(self):
        if not shutil.which("python3"):
            self.skipTest("no python3 on this machine")
        done = subprocess.run([str(self.shim), "doctor"], capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        answer = json.loads(done.stdout)
        self.assertIn("host_client", answer)

    def test_a_symlink_to_the_shim_still_finds_the_clone(self):
        """the url installer links one shim onto a path, so the shim cannot trust its own $0."""
        if not shutil.which("python3"):
            self.skipTest("no python3 on this machine")
        with tempfile.TemporaryDirectory() as d:
            link = pathlib.Path(d) / "heyphony"
            link.symlink_to(self.shim)
            done = subprocess.run([str(link), "status"], capture_output=True, text=True, timeout=120)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("provider", json.loads(done.stdout))

    def test_the_menu_pulls_termios_in_only_when_a_terminal_is_involved(self):
        """every command has to run on a host with no terminal, which is most of them."""
        source = (ROOT / "heyphony/src/setup/flow.py").read_text()
        self.assertNotIn("\nimport termios", source, "termios moved to the top level, so windows breaks")
        self.assertNotIn("\nimport tty", source)
        self.assertIn("import termios", source, "the interactive path lost its terminal handling")


class TestThePackageIsStandalone(unittest.TestCase):
    """the whole reason this repo exists: the package does not need the umbrella behind it."""

    def test_no_import_reaches_outside_the_package_or_the_standard_library(self):
        allowed = {"argparse", "base64", "email", "hashlib", "hmac", "http", "json", "os",
                   "pathlib", "re", "shutil", "sqlite3", "subprocess", "sys", "termios", "time",
                   "tty", "urllib", "xml"}
        for path in sorted((ROOT / "heyphony").rglob("*.py")):
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if not stripped.startswith(("import ", "from ")):
                    continue
                if stripped.startswith(("from heyphony", "import heyphony")):
                    continue
                module = stripped.split()[1].split(".")[0]
                self.assertIn(module, allowed,
                              f"{path.relative_to(ROOT)} imports {module}, which is not in the package")

    def test_the_umbrella_is_not_named_in_an_import_anywhere(self):
        for path in sorted((ROOT / "heyphony").rglob("*.py")):
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")):
                    self.assertNotIn("comms", stripped, f"{path.relative_to(ROOT)}: {stripped}")

    def test_one_version_number_for_the_code_and_the_package(self):
        import heyphony
        manifest = json.loads((ROOT / "npm/package.json").read_text())
        self.assertEqual(manifest["version"], heyphony.__version__,
                         "the npm package would ship under a version its own code does not claim")


class TestTheNpmPackageIsInstallable(unittest.TestCase):
    """the installable is code, so it gets tested like code. a bin entry pointing at nothing is the
    classic tarball that installs cleanly and runs nothing."""

    npm = ROOT / "npm"

    def node(self):
        exe = shutil.which("node")
        if not exe:
            self.skipTest("no node on this machine")
        return exe

    def test_the_bin_entry_points_at_a_file_that_exists(self):
        manifest = json.loads((self.npm / "package.json").read_text())
        self.assertEqual(list(manifest["bin"]), ["heyphony"])
        target = self.npm / manifest["bin"]["heyphony"]
        self.assertTrue(target.is_file(), "the bin entry points at nothing")
        self.assertTrue(os.access(target, os.X_OK), "the shim is not executable, so npm -g cannot link it")

    def test_the_files_list_ships_the_python_and_the_two_pages(self):
        manifest = json.loads((self.npm / "package.json").read_text())
        for entry in ("python/", "bin/", "readme.md", "agents.md"):
            self.assertIn(entry, manifest["files"], f"{entry} falls out of the tarball")
        self.assertIn("python3", (self.npm / "bin/heyphony.js").read_text(),
                      "the shim stopped naming the interpreter it needs")

    def test_the_bundle_copies_the_tree_and_leaves_the_caches_behind(self):
        self.node()
        done = subprocess.run([self.node(), str(self.npm / "scripts/bundle.js"), "--strict"],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        bundled = self.npm / "python/heyphony"
        self.assertTrue((bundled / "src/runner/cli.py").is_file())
        self.assertEqual(list(bundled.rglob("__pycache__")), [], "a cached .pyc does not belong in a tarball")
        self.assertEqual((bundled / "__init__.py").read_text().count("__version__"),
                         (ROOT / "heyphony/__init__.py").read_text().count("__version__"))

    def test_the_installed_shim_runs_the_bundled_code(self):
        node = self.node()
        subprocess.run([node, str(self.npm / "scripts/bundle.js"), "--strict"],
                       capture_output=True, text=True, timeout=120, check=True)
        version = subprocess.run([node, str(self.npm / "bin/heyphony.js"), "--version"],
                                 capture_output=True, text=True, timeout=120)
        self.assertEqual(version.returncode, 0, version.stderr)
        import heyphony
        self.assertEqual(version.stdout.strip(), heyphony.__version__)
        doctor = subprocess.run([node, str(self.npm / "bin/heyphony.js"), "doctor"],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        self.assertIn("host_client", json.loads(doctor.stdout))

    def test_the_shim_says_what_is_wrong_instead_of_crashing(self):
        """a shim that dies with a traceback on a python-less machine teaches nobody anything."""
        source = (self.npm / "bin/heyphony.js").read_text()
        for needle in ("ENOENT", "brew install python3", "HEYPHONY_PYTHON", "127"):
            self.assertIn(needle, source, f"the missing-interpreter path lost {needle!r}")

    def test_the_bundle_work_is_not_committed(self):
        """the copy is made at pack time. a committed copy is a second tree that drifts."""
        ignore = (ROOT / ".gitignore").read_text()
        self.assertIn("npm/python", ignore)
        self.assertIn("node_modules", ignore)
        self.assertIn("__pycache__", ignore)

    def test_the_url_installer_checks_its_two_prerequisites_first(self):
        script = (self.npm / "install.sh").read_text()
        for needle in ("python3", "sys.version_info >= (3, 8)", "curl", "HEYPHONY_HOME",
                       "HEYPHONY_REF", "refs/heads", "refs/tags", "ln -sf"):
            self.assertIn(needle, script, f"install.sh lost {needle!r}")
        self.assertNotIn("sudo", script, "an install that needs root is a different product")

    def test_the_installed_layout_is_the_one_the_installer_claims(self):
        """the shim resolves ../python relative to itself, and the installer must preserve that."""
        shim = (self.npm / "bin/heyphony.js").read_text()
        self.assertIn('path.join(pythonTree, "heyphony", "src", "runner", "cli.py")', shim)
        self.assertIn("heyphony.src.runner.cli", shim)


class TestThePagesSayHowToGetIt(unittest.TestCase):
    root_readme = ROOT / "readme.md"
    npm_readme = ROOT / "npm/readme.md"
    agents = ROOT / "npm/agents.md"

    def test_every_install_route_is_on_the_page(self):
        text = self.root_readme.read_text()
        for needle in ("npm/install.sh", "git clone", "npm pack", "npx heyphony", "bin/heyphony"):
            self.assertIn(needle, text, f"the root readme stopped mentioning {needle!r}")

    def test_the_page_does_not_claim_a_publish_that_has_not_happened(self):
        text = self.root_readme.read_text()
        self.assertIn("nothing here is on the npm registry yet", text)
        npm_page = self.npm_readme.read_text()
        self.assertIn("nothing is published to the npm registry", npm_page.lower(),
                      "the install page must not imply `npm i -g heyphony` works today")

    def test_the_package_is_not_sold_as_a_library(self):
        npm_page = self.npm_readme.read_text()
        self.assertIn('require("heyphony")', npm_page)
        self.assertIn("one executable", npm_page)

    def test_the_agent_page_hands_over_the_next_question_instead_of_a_menu(self):
        text = self.agents.read_text()
        for needle in ('"needs"', '"flag"', "do not loop", "only your human", "paying for the number",
                       "0600", "open messages --unread", "refused"):
            self.assertIn(needle, text, f"the agent page lost {needle!r}")

    def test_the_three_places_it_can_live_are_named_and_deferred(self):
        text = self.root_readme.read_text()
        self.assertIn("three places it can live", text)
        for needle in ("local computer", "cloud vm", "spawnable"):
            self.assertIn(needle, text, f"the readme stopped naming {needle!r}")
        self.assertIn("`setup` branch", text, "the instructions live on the setup branch, so say so")

    def test_no_page_picked_up_an_em_dash(self):
        for page in [self.root_readme, self.npm_readme, self.agents]:
            self.assertNotIn("\u2014", page.read_text(), f"{page.name} has an em dash")

    def test_the_package_page_admits_it_came_from_the_umbrella(self):
        """the prose names sibling lanes that live elsewhere, so the page has to say so."""
        text = (ROOT / "heyphony/readme.md").read_text()
        self.assertIn("this copy is the standalone package", text)
        self.assertIn("spawnables/tree/comms", text)

    def test_the_planned_branches_are_named_as_planned(self):
        text = self.root_readme.read_text()
        for needle in ("`comms`", "omnimeetings", "callheavy", "only `main` exists today"):
            self.assertIn(needle, text, f"the branch table lost {needle!r}")


class TestLinphoneConfig(unittest.TestCase):
    def test_rc_writes_the_sections_linphone_reads(self):
        text = linphone.rc_text("voip.ms", "+15550001111", "123456_agent", "hunter2", "chicago.voip.ms")
        for needle in ("[proxy_0]", "reg_proxy=sip:chicago.voip.ms", "reg_identity=sip:123456_agent@chicago.voip.ms",
                       "[auth_info_0]", "username=123456_agent", "passwd=hunter2", "domain=sip:chicago.voip.ms"):
            self.assertIn(needle, text)

    def test_rc_is_written_private(self):
        with tempfile.TemporaryDirectory() as d:
            path = linphone.write_rc("flowroute", "+15550002222", "u", "p", None, home=d)
            self.assertTrue(path.is_file())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_regional_server_is_not_guessed_silently(self):
        self.assertEqual(linphone.sip_host("voip.ms", "to2.voip.ms"), "to2.voip.ms")
        self.assertIn("voip.ms", linphone.sip_host("voip.ms"))
        with self.assertRaises(KeyError):
            linphone.sip_host("somebody-else")


class TestWhereTheNumberLives(unittest.TestCase):
    def test_the_default_endpoint_is_the_durable_host(self):
        plan = linphone.connection_plan("+15550001111")
        self.assertEqual(plan["endpoint"], "host")
        self.assertTrue(plan["survives_burn"])
        self.assertTrue(plan["rings_with_no_guest"])
        self.assertFalse(plan["secret_in_burn"])

    def test_a_guest_registration_is_allowed_but_named_as_a_liability(self):
        plan = linphone.connection_plan("+15550001111", "guest")
        self.assertTrue(plan["secret_in_burn"])
        self.assertFalse(plan["survives_burn"])
        self.assertEqual(plan["registrations"], 1)

    def test_one_did_is_one_registration_either_way(self):
        for endpoint in linphone.ENDPOINTS:
            self.assertEqual(linphone.connection_plan("+1555", endpoint)["registrations"], 1)

    def test_an_endpoint_we_do_not_model_is_refused(self):
        with self.assertRaises(KeyError):
            linphone.connection_plan("+1555", "somewhere")


class TestReaders(unittest.TestCase):
    def test_calls_are_read_and_named(self):
        with tempfile.TemporaryDirectory() as d:
            db = pathlib.Path(d) / "call-history.db"
            call_db(db, [("sip:caller@x", "sip:agent@y", 1, 42, "1700000000", None, 0, "abc"),
                         ("sip:bank@x", "sip:agent@y", 1, 0, "1700000100", None, 2, "def")])
            got = linphone.calls(db=db)
            self.assertEqual([c["direction"] for c in got], ["incoming", "incoming"])
            self.assertEqual({c["status"] for c in got}, {"success", "missed"})
            self.assertEqual(len(linphone.calls(db=db, missed_only=True)), 1)

    def test_sip_messages_table_is_read_but_is_not_the_inbox(self):
        with tempfile.TemporaryDirectory() as d:
            db = pathlib.Path(d) / "messages.db"
            message_db(db, [("sip:agent@y", "sip:x@z", 1, "hello", 1700000000, 0)])
            got = linphone.messages(db=db)
            self.assertEqual(got[0]["body"], "hello")
            self.assertFalse(got[0]["read"])

    def test_missing_db_is_an_empty_list_not_a_crash(self):
        self.assertEqual(linphone.calls(db="/nope/call-history.db"), [])


class TestInbox(unittest.TestCase):
    def test_a_retried_webhook_is_one_message(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "inbox.jsonl"
            entry = {"id": "m1", "from": "+1555", "body": "hi", "at": 1700000000}
            self.assertEqual(inbox.append(entry, path), (True, "stored"))
            self.assertEqual(inbox.append(entry, path), (False, "duplicate"))
            self.assertEqual(inbox.count(path), 1)

    def test_since_filters_on_the_provider_timestamp(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "inbox.jsonl"
            inbox.append({"id": "old", "at": 1000, "body": "old"}, path)
            inbox.append({"id": "new", "at": 1700000000, "body": "new"}, path)
            self.assertEqual([m["id"] for m in inbox.read(path, since_days=1)], [])


class TestWebhook(unittest.TestCase):
    def test_normalize_pulls_the_flat_shape_and_keeps_raw(self):
        entry = phone_catcher.normalize({"from": "+1555", "to": "+1", "body": "ping", "id": "x1"})
        self.assertEqual((entry["sender"], entry["body"], entry["id"]), ("+1555", "ping", "x1"))
        self.assertEqual(entry["channel"], "sms")
        self.assertIn("from", entry["raw"])

    def test_normalize_walks_the_nested_shape(self):
        entry = phone_catcher.normalize({"data": {"id": "y1", "attributes": {
            "from": "+1666", "body": "nested", "timestamp": "1700000000"}}})
        self.assertEqual((entry["id"], entry["body"]), ("y1", "nested"))

    def test_an_unknown_payload_still_gets_stored(self):
        entry = phone_catcher.normalize({"weird": {"thing": 1}})
        self.assertIn("raw", entry)
        self.assertIsNotNone(entry["at"])


class TestProviderClaims(unittest.TestCase):
    def test_offline_capabilities_are_data_not_prose(self):
        self.assertTrue(providers.works_while_off("voip.ms")["voicemail"])
        self.assertFalse(providers.works_while_off("flowroute")["voicemail"])
        for name in providers.PROVIDERS:
            self.assertFalse(providers.profile(name)["verified"], name)

    def test_otp_is_refused_for_a_voice_did(self):
        self.assertEqual(providers.otp_viability("sip-did")["viable"], "no")

    def test_markup_never_changes_the_classification(self):
        for name in providers.PROVIDERS:
            self.assertEqual(providers.still_voip(name)["number_type"], "voip")


class TestGetters(unittest.TestCase):
    def test_signal_is_the_first_getter(self):
        self.assertIn("signal", getters.available())

    def test_linking_needs_no_number_at_all(self):
        plan = getters.plan("signal", "link-desktop", env={})
        self.assertTrue(plan["gettable"])
        self.assertEqual(plan["missing"], [])

    def test_the_phone_signup_is_the_default_and_needs_the_did(self):
        self.assertEqual(getters.plan("signal", None, {})["path"], "phone-signup")
        self.assertFalse(getters.plan("signal", "phone-signup", {})["gettable"])
        self.assertTrue(getters.plan("signal", "phone-signup", {"HEYPHONY_SIP_DID": "+1555"})["gettable"])

    def test_the_code_is_read_from_heyphony_not_a_handset(self):
        plan = getters.plan("signal", "phone-signup", {"HEYPHONY_SIP_DID": "+1555"})
        cmds = " ".join(step["cmd"] for step in plan["steps"])
        self.assertIn("heyphony open messages", cmds)
        self.assertIn("durable", getters.available()["signal"]["flow"][0])

    def test_the_desktop_links_as_a_named_device(self):
        cmds = " ".join(s["cmd"] for s in getters.plan("signal", "link-desktop", {})["steps"])
        self.assertIn("device_name=heyphony-desktop", cmds)

    def test_voip_strictness_is_described_honestly(self):
        risky = getters.available()["signal"]["paths"]["register-number"]["why_risky"]
        self.assertIn("less strict about voip", risky)
        self.assertIn("never a promise", risky)

    def test_registering_needs_the_did_heyphony_holds(self):
        self.assertFalse(getters.plan("signal", "register-number", env={})["gettable"])
        self.assertTrue(getters.plan("signal", "register-number", {"HEYPHONY_SIP_DID": "+1555"})["gettable"])

    def test_an_unknown_getter_says_what_exists(self):
        out = getters.plan("carrier-pigeon", env={})
        self.assertFalse(out["gettable"])
        self.assertIn("signal", out["known"])

    def test_a_dry_run_executes_nothing(self):
        out = getters.run("signal", "link-desktop", env={})
        self.assertTrue(out["dry"])
        self.assertTrue(all(not step["executed"] for step in out["ran"]))

    def test_the_qr_scan_stays_a_human_act(self):
        out = getters.run("signal", "link-desktop", env={})
        self.assertTrue(any("scan" in who.lower() for who in out["needs_a_human"]))
        self.assertIn("qrcodelink", "".join(s["cmd"] for s in out["steps"]))

    def test_the_recipe_pins_commands_verified_upstream(self):
        recipe = getters.available()["signal"]
        joined = " ".join(step["cmd"] for step in recipe["install"])
        self.assertIn("MODE=native", joined)
        self.assertIn("bbernhard/signal-cli-rest-api", joined)
        self.assertIn("/v1/qrcodelink", " ".join(step["cmd"] for step in recipe["paths"]["link-desktop"]["steps"]))
        self.assertIn("/v2/send", recipe["install"][0]["source"])

    def test_the_getter_claims_no_bot_api(self):
        self.assertIn("bot-api", getters.available()["signal"]["refused"])


    def test_telephony_setup_advertises_the_getter(self):
        self.assertIn("heyphony get signal", telephony_cli.SETUP["get"]["commands"])


    def test_telegram_is_the_second_ramp_and_it_is_two_rails(self):
        recipe = getters.available()["telegram"]
        self.assertEqual(list(recipe["paths"]), ["bot", "user-account"])
        self.assertEqual(getters.plan("telegram", None, {})["path"], "bot",
                         "the bot is the rail telegram supports, so it is the default")
        bot = getters.plan("telegram", "bot", env={})
        self.assertTrue(bot["gettable"], "the bot rail needs no number, so it needs no did")
        self.assertFalse(recipe["paths"]["bot"]["needs_number"])
        self.assertFalse(getters.plan("telegram", "user-account", {})["gettable"])
        self.assertTrue(getters.plan("telegram", "user-account", {"HEYPHONY_SIP_DID": "+1555"})["gettable"])
        self.assertEqual(recipe["state"], "designed")
        for refused in ("user-api-id-as-a-bot", "bulk-broadcast", "second-account-after-a-ban"):
            self.assertIn(refused, recipe["refused"])
        self.assertIn("refusal", recipe["paths"]["user-account"]["why_risky"],
                      "the account path has to say it can be refused, not imply it will work")

    def test_get_list_says_what_each_path_needs(self):
        """the list is the first thing an agent reads, so it must not need a second command to be useful."""
        from heyphony.src.runner import cli as telephony_cli
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            telephony_cli.main(["get", "--list"])
        answer = json.loads(buffer.getvalue())
        self.assertEqual(set(answer["getters"]), {"signal", "telegram"})
        bot = answer["getters"]["telegram"]["paths"]["bot"]
        self.assertFalse(bot["needs_number"])
        self.assertEqual(bot["gate_env"], "TELEGRAM_BOT_TOKEN")
        user = answer["getters"]["telegram"]["paths"]["user-account"]
        self.assertTrue(user["needs_number"])
        self.assertNotIn("link-device", answer["usage"],
                         "the usage line must not name one getter's paths as if they were all of them")

    def test_the_onramp_page_names_both_ramps(self):
        text = pathlib.Path("heyphony/src/onramp/readme.md").read_text()
        for needle in ("## signal, which is built", "## telegram, which is two rails",
                       "webhook", "botfather", "heyphony get telegram"):
            self.assertIn(needle, text, f"the onramp page lost {needle!r}")
        self.assertIn("telegram.json", str(list(pathlib.Path("heyphony/src/onramp").glob("*.json"))))


class TestOpeningTheInboxes(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.home = tempfile.mkdtemp()
        from heyphony.src.manage import inbox as store
        self.store = store
        self.path = pathlib.Path(self.home) / "telephony" / "inbox.jsonl"
        store.append({"id": "a1", "channel": "sms", "sender": "+1555",
                      "body": "your signal code is 123456", "at": 1700000000}, self.path)
        store.append({"id": "a2", "channel": "sms", "sender": "+1666", "body": "hello", "at": 1700000100}, self.path)

    def test_rows_are_numbered_and_previewed(self):
        from heyphony.src.manage import views
        out = views.messages(home=self.home, path=self.path)
        self.assertEqual([r["n"] for r in out["rows"]], [1, 2])
        self.assertEqual(out["rows"][0]["from"], "+1666")
        self.assertTrue(out["rows"][0]["preview"])

    def test_the_unread_mark_is_ours_because_the_provider_does_not_track_it(self):
        from heyphony.src.manage import views
        self.assertEqual(views.messages(home=self.home, path=self.path)["unread_total"], 2)
        views.messages(home=self.home, path=self.path, do_mark=[1])
        self.assertEqual(views.messages(home=self.home, path=self.path, unread=True)["count"], 1)

    def test_show_expands_exactly_one_body(self):
        from heyphony.src.manage import views
        out = views.messages(home=self.home, path=self.path, show=2)
        self.assertIn("signal code", out["message"]["body"])

    def test_a_thread_filter_narrows_to_one_number(self):
        from heyphony.src.manage import views
        out = views.messages(home=self.home, path=self.path, thread="+1555")
        self.assertEqual(out["count"], 1)

    def test_voicemail_reads_its_sidecar_and_never_invents_a_transcript(self):
        from heyphony.src.manage import views
        folder = pathlib.Path(self.home) / "telephony" / "voicemail"
        folder.mkdir(parents=True)
        (folder / "vm1.wav").write_bytes(b"RIFF")
        (folder / "vm1.json").write_text(json.dumps({"from": "+1777", "seconds": 9, "transcript": "call me back"}))
        (folder / "vm2.wav").write_bytes(b"RIFF")
        rows = views.voicemail(home=self.home)["rows"]
        self.assertEqual(len(rows), 2)
        self.assertTrue(any(r["transcript"] == "call me back" for r in rows))
        self.assertTrue(any(r["transcript"] == "" for r in rows))

    def test_the_call_log_is_empty_rather_than_wrong_without_a_database(self):
        from heyphony.src.manage import views
        out = views.calls(home=self.home)
        self.assertEqual((out["count"], out["rows"]), (0, []))

    def test_open_is_one_command_for_all_three(self):
        from heyphony.src.manage import views
        self.assertEqual(views.messages(home=self.home, path=self.path)["inbox"], "messages")
        self.assertEqual(views.calls(home=self.home)["inbox"], "calls")
        self.assertEqual(views.voicemail(home=self.home)["inbox"], "voicemail")


class TestTheDirectoryExplainsItself(unittest.TestCase):
    """the complaint that started this: python files, no way to see how the thing runs."""

    root = pathlib.Path(__file__).resolve().parent.parent
    hey = root / "heyphony"

    def test_the_map_exists_and_is_a_map(self):
        text = (self.hey / "directory.md").read_text()
        self.assertGreaterEqual(text.count("```mermaid"), 3, "the map lost its diagrams")
        for needle in ("setup", "manage", "onramp", "src/", "runner", "linphone",
                       "turnedon", "turnedoff", "inbox", "outgoing", "commands"):
            self.assertIn(needle, text, f"the map does not mention {needle}")
        self.assertNotIn("—", text)

    def test_setup_and_manage_are_drawn_as_separate_flows(self):
        """one flow for getting a number, one for living with it. conflating them is how it got confusing."""
        text = (self.hey / "directory.md").read_text()
        self.assertIn("the setup flow", text)
        self.assertIn("the manage flow", text)
        setup = text.split("### the setup flow", 1)[1].split("### the manage flow", 1)[0]
        self.assertIn("provision", setup, "the buy-a-number branch is missing")
        self.assertIn("sip did", setup, "the bring-a-number branch is missing")
        manage = text.split("### the manage flow", 1)[1]
        self.assertIn("is the host up", manage)
        self.assertIn("no live calls", manage)

    def test_every_folder_that_holds_code_says_what_it_is_for(self):
        for folder in ("src", "src/runner", "src/linphone", "src/setup", "src/manage", "src/onramp",
                       "src/setup/test", "src/setup/commands", "src/manage/turnedon",
                       "src/manage/turnedoff", "src/manage/inbox", "src/manage/outgoing"):
            page = self.hey / folder / "readme.md"
            self.assertTrue(page.is_file(), f"{folder} has no readme.md")
            self.assertGreater(len(page.read_text()), 400, f"{folder}/readme.md says nothing")

    def test_no_module_sits_where_a_description_folder_would(self):
        """a folder and a module with one name is a trap: the module wins, then someone adds an __init__."""
        for folder in self.hey.rglob("*"):
            if not folder.is_dir():
                continue
            for page in folder.glob("*.py"):
                clash = folder / page.stem
                if clash.is_dir() and (clash / "__init__.py").is_file():
                    self.fail(f"{clash} would shadow {page}")

    def test_the_code_lives_under_src_and_nothing_else_does(self):
        loose = sorted(p.name for p in self.hey.glob("*.py") if p.name != "__init__.py")
        self.assertEqual(loose, [], f"modules outside src: {loose}")

    def test_the_off_routing_page_matches_the_vendor_table(self):
        """the table a person reads and the data the code routes on must be the same table."""
        from heyphony.src import providers
        text = (self.hey / "src/manage/turnedoff/readme.md").read_text()
        for name in providers.inbox_providers():
            self.assertIn(f"| {name} |", text, f"{name} is missing from the off-routing table")
        for name in ("voyced", "voxacall", "bitcall"):
            self.assertIn(f"| {name} |", text)
        for name, facts in ((n, providers.profile(n)["works_while_off"]) for n in providers.PROVIDERS):
            for row in text.splitlines():
                if row.startswith(f"| {name} |"):
                    cells = [c.strip() for c in row.strip("|").split("|")]
                    want = ("yes" if facts["texts"] else "no",
                            "yes" if facts["voicemail"] else "no",
                            "yes" if facts["live_calls"] else "no")
                    self.assertEqual(tuple(cells[1:4]), want, f"{name} routing drifted: {row}")
                    break
            else:
                self.fail(f"{name} has no row")

    def test_the_command_index_names_the_commands_that_exist(self):
        from heyphony.src.runner import cli
        parser = cli.build_parser()
        subs = set()
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                subs |= set(action.choices)
        table = (self.hey / "src/setup/commands/readme.md").read_text()
        for name in subs:
            self.assertIn(f"`heyphony {name}", table, f"{name} exists and is not in the index")
        for absent in ("heyphony send", "heyphony call`"):
            self.assertIn(absent, table, f"the index stopped declaring {absent} missing")

    def test_the_prose_never_claims_a_lane_is_proven(self):
        for page in self.hey.rglob("*.md"):
            text = page.read_text().lower()
            self.assertNotIn("—", text, f"{page} picked up an em dash")
        off = (self.hey / "src/manage/turnedoff/readme.md").read_text().lower()
        self.assertIn("no live calls", (self.hey / "directory.md").read_text().lower())
        self.assertIn("only some of them offer it", off)


class TestTheCatcherKnowsEveryPath(unittest.TestCase):
    def test_a_provider_path_is_recognised_and_a_stranger_is_not(self):
        from heyphony.src.manage import catcher
        for name in ("flowroute", "anveo", "signalwire", "questblue", "bulkvs"):
            self.assertEqual(catcher.provider_of(f"/sms/{name}?x=1"), name)
        self.assertIsNone(catcher.provider_of("/sms/twilio"))
        self.assertIsNone(catcher.provider_of("/sms"))
        self.assertIsNone(catcher.provider_of("/email"))


class TestTheProvisioningChainStopsBeforeItSpends(unittest.TestCase):
    def run_cli(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = telephony_cli.main(argv)
        return code, out.getvalue()

    def test_areas_carry_stock_and_prices_in_dollars(self):
        from heyphony.src.setup import provision
        row = provision._area_row({"AREA_ID": "191.195.165.31.230", "AREA_CODE": "256",
                                   "AREA_NAME": "ALBERTVILLE", "STOCK": "49",
                                   "rate_plans": [{"RATE_PLAN_ID": "SU", "RATE_PLAN_NAME": "Service Unlimited",
                                                   "MONTHLY100": "149", "SETUP100": "249"}]})
        self.assertEqual((row["area_code"], row["stock"]), ("256", 49))
        self.assertEqual(row["rate_plans"][0]["monthly_usd"], 1.49)
        self.assertEqual(row["rate_plans"][0]["setup_usd"], 2.49)

    def test_apply_asks_for_stock_and_stops_at_the_order(self):
        from heyphony.src.setup import provision
        saved = {k: os.environ.pop(v, None) for k, v in provision.ENV.items()}
        try:
            answer = provision.plan("212", apply=True)
            self.assertFalse(answer["applied"])
            self.assertEqual(answer["missing"], ["userkey", "email", "phrase"])
            self.assertIn("nothing was asked", answer["why"])
        finally:
            for key, value in saved.items():
                if value is not None:
                    os.environ[provision.ENV[key]] = value
        steps = provision.plan("212")["steps"]
        self.assertEqual([(s["action"], s["free"]) for s in steps],
                         [("ANVEO.AREAS.LIST", True), ("DID.ORDER", False), ("DID.UPDATE", True)])

    def test_the_purchase_step_is_parked_rather_than_forgotten(self):
        from heyphony.src.setup import provision
        parked = provision.plan("212", purchase=True)
        self.assertFalse(parked["ok"])
        self.assertEqual(parked["purchase"], "parked")
        self.assertIn("payment rail", parked["why"])
        self.assertIn("hooks anveo --apply", parked["instead"])

    def test_area_selection_is_first_class(self):
        from heyphony.src.setup import provision
        self.assertEqual(sorted(provision.DID_TYPES), ["GEOGRAPHIC", "MOBILE", "NATIONAL", "TOLLFREE"])
        plan = provision.plan("212", area_name="new york", country_id="US")
        self.assertEqual(plan["area_name"], "new york")
        self.assertIn("param[COUNTRY_ID]=US", urllib.parse.unquote(plan["steps"][0]["as_curl"]))


class TestTheSetupPlanCoversVoicemailAndCatching(unittest.TestCase):
    def test_a_connect_line_is_not_the_whole_errand(self):
        from heyphony.src.setup import flow as flow
        plan = flow.plan_sip("voip.ms", "+12125551234")
        self.assertEqual(plan["catching"]["kind"], "email")
        self.assertIn("heyphony serve", plan["catching"]["serve"])
        self.assertIn("carrier", plan["voicemail"]["where"])
        self.assertEqual(plan["launcher"]["tabs"], ["caught messages", "voicemail", "calls"])
        for step in ("arm the text hook", "point voicemail", "heyphony app"):
            self.assertTrue(any(step in s for s in plan["steps"]), step)
        anveo = flow.plan_sip("anveo", "+12125551234")
        self.assertIn("url-forward", anveo["catching"]["kind"])
        flowroute = flow.plan_sip("flowroute", "+12125551234")
        self.assertIn("no carrier fallback", flowroute["voicemail"]["where"])


class TestTheLauncher(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.inbox = self.tmp / "inbox.jsonl"
        self.voice = self.tmp / "voicemail"
        self.voice.mkdir()
        for entry in ({"id": "sms:1", "channel": "sms", "direction": "inbound",
                       "sender": "+15551230000", "recipient": "+15559990000", "subject": None,
                       "body": "are you free at 3?", "at": 1793500000, "thread": "+15551230000",
                       "reply_to": None, "raw": {"provider": "voip.ms"}},
                      {"id": "sms:2", "channel": "sms", "direction": "inbound",
                       "sender": "+15554440000", "recipient": "+15559990000", "subject": None,
                       "body": "invoice attached", "at": 1793400000, "thread": "+15554440000",
                       "reply_to": None, "raw": {"provider": "flowroute"}}):
            inbox.append(entry, path=self.inbox)

    def test_texts_and_voicemail_merge_into_one_thread_per_person(self):
        from heyphony.src.runner import gui as launcher
        raw = ("From: voipms@voip.ms\nSubject: VOICEMAIL from 15551230000\n"
               "Date: Sun, 01 Nov 2026 09:00:00 +0000\nContent-Type: text/plain\n\n"
               "new voicemail, 14 seconds. transcript: call me back about the invoice.\n")
        stored = launcher.import_email(raw, save_dir=self.voice, path=self.inbox)
        self.assertTrue(stored["stored"])
        self.assertEqual(stored["kind"], "voicemail")
        threads = launcher.threads(path=self.inbox, voicemail_dir=self.voice)["threads"]
        self.assertEqual([t["peer"] for t in threads], ["+15551230000", "+15554440000"])
        first = threads[0]
        self.assertEqual(first["kinds"], ["sms", "voicemail"])
        self.assertEqual(first["count"], 2)
        detail = launcher.thread("+15551230000", path=self.inbox, voicemail_dir=self.voice)
        self.assertEqual([i["kind"] for i in detail["items"]], ["sms", "voicemail"])

    def test_a_forwarded_voicemail_is_not_counted_twice(self):
        """the message and its recording are one thing to a person, so the thread shows it once."""
        from heyphony.src.runner import gui as launcher
        raw = ("From: voipms@voip.ms\nSubject: VOICEMAIL from 15559998888\n"
               "Date: Sun, 01 Nov 2026 09:00:00 +0000\nMIME-Version: 1.0\n"
               "Content-Type: multipart/mixed; boundary=B\n\n--B\nContent-Type: text/plain\n\n"
               "voicemail, 14 seconds\n--B\nContent-Type: audio/wav\n"
               "Content-Transfer-Encoding: base64\n"
               "Content-Disposition: attachment; filename=\"vm.wav\"\n\n"
               "UklGRiQAAABXQVZFZm10IBAAAAABAAEAgD4AAAB9AAACABAAZGF0YQAAAAA=\n--B--\n")
        stored = launcher.import_email(raw, save_dir=self.voice, path=self.inbox)
        self.assertTrue(stored["stored"])
        detail = launcher.thread("+15559998888", path=self.inbox, voicemail_dir=self.voice)
        self.assertEqual([i["kind"] for i in detail["items"]], ["voicemail"])
        bucket = next(t for t in launcher.threads(path=self.inbox, voicemail_dir=self.voice)["threads"]
                      if t["peer"] == "+15559998888")
        self.assertEqual(bucket["count"], 1)
        # the audio is still readable in the voicemail tab, which is where a recording belongs
        self.assertEqual(launcher.views.voicemail(path=self.voice)["count"], 1)

    def test_a_reply_is_a_draft_with_a_route_and_never_a_send(self):
        from heyphony.src.runner import gui as launcher
        answer = launcher.draft("+15551230000", "sure, 3 works", path=self.inbox)
        self.assertFalse(answer["applied"])
        self.assertEqual(answer["provider"], "voip.ms")
        self.assertFalse(answer["outbound"]["now"])
        self.assertIn("no outbound api path", answer["outbound"]["why"])
        self.assertIn("draft", answer["note"])

    def test_voicemail_rows_carry_a_time_a_person_can_read(self):
        from heyphony.src.runner import gui as launcher
        raw = ("From: voipms@voip.ms\nSubject: VOICEMAIL from 15557776666\n"
               "Date: Sun, 01 Nov 2026 09:00:00 +0000\nMIME-Version: 1.0\n"
               "Content-Type: multipart/mixed; boundary=B\n\n--B\nContent-Type: text/plain\n\n"
               "voicemail, 8 seconds\n--B\nContent-Type: audio/wav\n"
               "Content-Transfer-Encoding: base64\n"
               "Content-Disposition: attachment; filename=\"vm2.wav\"\n\n"
               "UklGRiQAAABXQVZFZm10IBAAAAABAAEAgD4AAAB9AAACABAAZGF0YQAAAAA=\n--B--\n")
        launcher.import_email(raw, save_dir=self.voice, path=self.inbox)
        row = launcher.voicemails(path=self.inbox, voicemail_dir=self.voice)["rows"][0]
        self.assertRegex(row["when"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")

    def test_app_json_answers_and_exits_instead_of_serving_forever(self):
        """a flag called --json that binds a port and never returns is a hang, not an answer."""
        from heyphony.src.runner import cli as telephony_cli
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            started = time.time()
            code = telephony_cli.main(["app", "--json"])
            elapsed = time.time() - started
        self.assertEqual(code, 0)
        self.assertLess(elapsed, 5, "app --json blocked, so an agent calling it times out")
        answer = json.loads(buffer.getvalue())
        self.assertFalse(answer["serving"])
        self.assertEqual(answer["tabs"], ["messages", "voicemail", "calls"])
        self.assertEqual(answer["reply"], "drafts only")
        self.assertIn("counts", answer)
        self.assertEqual(set(answer["counts"]), {"threads", "voicemail", "calls", "missed"})
        self.assertIn("start_it", answer, "the answer must say how to actually start the page")

    def test_the_page_serves_tabs_and_json(self):
        import threading
        import urllib.request
        from heyphony.src.runner import gui as launcher
        server = launcher.serve(port=0, path=self.inbox, voicemail_dir=self.voice)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as page:
                html = page.read().decode()
            for tab in ("caught messages", "voicemail", "calls"):
                self.assertIn(tab, html)
            self.assertIn("drafts only", launcher.providers_seen(path=self.inbox)["reply"])
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/threads") as answer:
                self.assertEqual(len(json.load(answer)["threads"]), 2)
            body = json.dumps({"peer": "+15551230000", "body": "hi"}).encode()
            request = urllib.request.Request(f"http://127.0.0.1:{port}/api/reply", data=body,
                                            headers={"content-type": "application/json"})
            with urllib.request.urlopen(request) as answer:
                self.assertFalse(json.load(answer)["applied"])
        finally:
            server.shutdown()
            server.server_close()

    def test_a_carrier_email_keeps_its_audio_and_never_guesses_a_sender(self):
        from heyphony.src.manage import mailparse
        raw = ("From: voipms@voip.ms\nSubject: VOICEMAIL from 12125550123\n"
               "Date: Sun, 01 Nov 2026 10:00:00 +0000\nMIME-Version: 1.0\n"
               "Content-Type: multipart/mixed; boundary=B\n\n--B\n"
               "Content-Type: text/plain\n\nvoicemail, 9 seconds\n--B\n"
               "Content-Type: audio/wav\nContent-Transfer-Encoding: base64\n"
               "Content-Disposition: attachment; filename=\"vm.wav\"\n\n"
               "UklGRiQAAABXQVZFZm10IBAAAAABAAEAgD4AAAB9AAACABAAZGF0YQAAAAA=\n--B--\n")
        item = mailparse.parse(raw, save_dir=self.voice)
        self.assertEqual(item["kind"], "voicemail")
        self.assertEqual(item["sender"], "+12125550123")
        self.assertTrue(pathlib.Path(item["audio"]["path"]).is_file())
        self.assertTrue(pathlib.Path(mailparse.sidecar_for(item)).is_file())
        anon = mailparse.parse("From: x@y\nSubject: hello\n\nno number in here\n")
        self.assertIsNone(anon["sender"])
        self.assertEqual(anon["kind"], "email")


class TestProvisioningIsACliWhereTheProviderAllowsIt(unittest.TestCase):
    def run_cli(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = telephony_cli.main(argv)
        return code, out.getvalue()

    def test_anveo_signature_matches_their_published_example(self):
        from heyphony.src.setup import provision
        self.assertEqual(provision.signature("some@email.com", "my secure phrase"),
                         "396cdfaff3491f457b95e51a5ebd89ad516d623d")

    def test_anveo_answers_parse_into_areas_and_numbers(self):
        from heyphony.src.setup import provision
        areas = provision.parse(
            '<RESPONSE><RESULT>SUCCESS</RESULT><AREAS>'
            '<AREA AREA_NAME="ALBERTVILLE" AREA_ID="191.195.165.31.230" AREA_CODE="256" STOCK="49">'
            '<RATE_PLAN RATE_PLAN_ID="VALUE" RATE_PLAN_NAME="Value" MONTHLY100="149" SETUP100="249" />'
            '<RATE_PLAN RATE_PLAN_ID="SU" RATE_PLAN_NAME="Service Unlimited" MONTHLY100="149" SETUP100="249" />'
            '</AREA></AREAS></RESPONSE>')
        self.assertEqual(areas["result"], "SUCCESS")
        self.assertEqual(areas["areas"][0]["AREA_CODE"], "256")
        self.assertEqual(areas["areas"][0]["rate_plans"][1]["RATE_PLAN_ID"], "SU")
        bought = provision.parse(
            '<RESPONSE><RESULT>SUCCESS</RESULT><DIDS>'
            '<DID E164="12121111111" DID_TYPE="GEOGRAPHIC" SMS_URL="" STATUS="Active" AREA_CODE="212" />'
            '</DIDS></RESPONSE>')
        self.assertEqual(bought["dids"][0]["E164"], "12121111111")

    def test_provisioning_is_a_plan_without_apply_and_names_its_credentials(self):
        from heyphony.src.setup import provision
        saved = {k: os.environ.pop(v, None) for k, v in provision.ENV.items()}
        try:
            plan = provision.plan("212", sms_url="https://host:8099/sms/anveo?from=$[from]$")
            self.assertFalse(plan["applied"])
            self.assertEqual(sorted(plan["missing"]), ["email", "phrase", "userkey"])
            self.assertEqual([step["action"] for step in plan["steps"]],
                             ["ANVEO.AREAS.LIST", "DID.ORDER", "DID.UPDATE"])
            self.assertIn("DID.ORDER", plan["steps"][1]["as_curl"])
            self.assertIn("$[from]$", plan["steps"][2]["params"]["SMS_URL"])
            self.assertIn("--apply", plan["next"])
            bad = provision.plan("212", did_type="MAGIC")
            self.assertFalse(bad["ok"])
            self.assertIn("did_type", bad["why"])
        finally:
            for key, value in saved.items():
                if value is not None:
                    os.environ[provision.ENV[key]] = value

    def test_only_anveo_is_provisionable_from_the_cli_and_the_plan_says_which(self):
        code, text = self.run_cli(["provision", "--provider", "anveo", "--area-code", "212"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(text)["provider"], "anveo")
        from heyphony.src.setup import flow as flow
        anveo = flow.plan_sip("anveo", "+12125551234")
        self.assertEqual(anveo["provisioning"]["now"], "cli")
        self.assertIn("setup provision", anveo["provisioning"]["command"])
        self.assertEqual(anveo["provisioning"]["stops_before"], "DID.ORDER")
        self.assertFalse(anveo["provisioning"]["spends_money"])
        flowroute = flow.plan_sip("flowroute", "+12125551234")
        self.assertEqual(flowroute["provisioning"]["now"], "browser")

    def test_arming_anveos_sms_refuses_without_credentials_and_shows_the_call(self):
        from heyphony.src.setup import provision
        from heyphony.src.setup import routes
        saved = {k: os.environ.pop(v, None) for k, v in provision.ENV.items()}
        try:
            answer = routes.apply_hook("anveo", "https://host:8099", "+12125551234")
            self.assertFalse(answer["applied"])
            self.assertEqual(answer["missing"], ["userkey", "email", "phrase"])
            self.assertIn("DID.UPDATE", answer["as_curl"])
            self.assertIn("FILTER.E164", answer["as_curl"].replace("%5B", "[").replace("%5D", "]"))
            no_did = routes.apply_hook("anveo", "https://host:8099")
            self.assertFalse(no_did["applied"])
            self.assertIn("--did", no_did["why"])
        finally:
            for key, value in saved.items():
                if value is not None:
                    os.environ[provision.ENV[key]] = value


class TestTheGuidedSetup(unittest.TestCase):
    """a menu for a person, a json question for a process, one plan either way."""

    def run_cli(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = telephony_cli.main(argv)
        return code, out.getvalue()

    def test_the_menu_is_every_provider_the_routes_know_about(self):
        from heyphony.src.setup import routes
        keys = [c["key"] for c in setup_flow.PROVIDER_CHOICES]
        self.assertEqual(keys, ["voip.ms", "flowroute", "anveo", "signalwire", "questblue",
                                "bulkvs", "jmp.chat", "voyced", "voxacall", "bitcall"])
        self.assertEqual(sorted(keys), sorted(routes.ROUTES), "the menu and the routes cannot drift")
        self.assertTrue(all(c.get("group") for c in setup_flow.PROVIDER_CHOICES))
        groups = {c["group"] for c in setup_flow.PROVIDER_CHOICES}
        self.assertEqual(groups, {"texts reach an inbox", "voice only, no inbox"})
        self.assertEqual([c["key"] for c in setup_flow.DID_CHOICES], ["existing", "new"])

    def test_a_piped_answer_picks_by_number_and_enter_takes_the_default(self):
        def keyed(answer):
            return setup_flow.select("provider", setup_flow.PROVIDER_CHOICES,
                                     stream_in=io.StringIO(answer), stream_out=io.StringIO(), tty=False)
        self.assertEqual(keyed("2\n"), "flowroute")
        self.assertEqual(keyed("\n"), "voip.ms")
        self.assertEqual(keyed("voip.ms\n"), "voip.ms")

    def test_garbage_is_asked_again_rather_than_accepted(self):
        self.assertEqual(setup_flow.select("provider", setup_flow.PROVIDER_CHOICES,
                                           stream_in=io.StringIO("nope\n2\n"),
                                           stream_out=io.StringIO(), tty=False), "flowroute")

    def test_a_terminal_we_cannot_read_keys_from_still_gets_a_menu(self):
        out = io.StringIO()
        self.assertEqual(setup_flow.select("provider", setup_flow.PROVIDER_CHOICES,
                                           stream_in=io.StringIO("1\n"), stream_out=out, tty=True),
                         "voip.ms")
        self.assertIn("1. voip.ms", out.getvalue())

    def test_an_existing_did_gives_the_connect_line(self):
        plan = setup_flow.plan_sip("voipms", did="+15551234567")
        self.assertEqual(plan["provider"], "voip.ms")
        self.assertEqual(plan["did"]["source"], "existing")
        self.assertIn("--provider voip.ms --did +15551234567", plan["connect"])
        self.assertFalse(plan["verified"])
        self.assertEqual(plan["number_type"], "voip")

    def test_a_new_number_goes_to_the_browser_and_says_what_is_later(self):
        plan = setup_flow.plan_sip("flowroute", new=True)
        self.assertEqual(plan["did"]["source"], "new")
        self.assertTrue(plan["browser"]["url"].startswith("https://"))
        self.assertFalse(plan["browser"]["deep_link_verified"])
        self.assertEqual(plan["provisioning"]["now"], "browser")
        self.assertIn("cli", plan["provisioning"]["later"])

    def test_e164_is_enforced_before_a_plan_exists(self):
        self.assertTrue(setup_flow.valid_did("+15551234567"))
        self.assertFalse(setup_flow.valid_did("5551234"))
        self.assertFalse(setup_flow.valid_did("+1"))

    def test_a_process_with_no_flags_gets_the_next_question_not_a_hang(self):
        code, text = self.run_cli(["setup", "select", "sip"])
        self.assertEqual(code, 0)
        answer = json.loads(text)
        self.assertFalse(answer["ok"])
        self.assertEqual(answer["needs"], "provider")
        self.assertIn("bulkvs", [o["key"] for o in answer["options"]])
        self.assertIn("jmp.chat", [o["key"] for o in answer["options"]])

    def test_a_process_with_the_flags_gets_the_plan(self):
        code, text = self.run_cli(["setup", "select", "sip", "--provider", "voipms",
                                   "--did", "+15551234567", "--json"])
        self.assertEqual(code, 0)
        plan = json.loads(text)
        self.assertIn("+15551234567", plan["connect"])
        self.assertEqual(plan["rail"], "sip")

    def test_a_provider_we_do_not_hold_is_refused_with_the_ones_we_do(self):
        code, text = self.run_cli(["setup", "select", "sip", "--provider", "twilio"])
        self.assertEqual(code, 1)
        options = json.loads(text)["options"]
        self.assertIn("bulkvs", options)
        self.assertNotIn("twilio", options)

    def test_only_the_providers_that_can_receive_are_called_an_inbox(self):
        inbox = set(providers.inbox_providers())
        self.assertEqual(inbox, {"voip.ms", "flowroute", "anveo", "signalwire", "questblue",
                                 "bulkvs", "jmp.chat"})
        for name, needle in (("voyced", "voice number until a real text lands"),
                             ("voxacall", "not an inbox"),
                             ("bitcall", "cannot be the inbox")):
            entry = providers.profile(name)
            self.assertEqual(entry["text_style"], "none", name)
            self.assertFalse(entry["works_while_off"]["texts"], name)
            self.assertIn(needle, entry["note"], name)
        self.assertEqual(providers.profile("jmp.chat")["text_style"], "xmpp")
        self.assertEqual(providers.profile("jmp.chat")["did_usd_month"], 4.99)
        self.assertEqual(providers.profile("bulkvs")["did_usd_month"], 0.06)

    def test_every_route_says_what_a_person_pastes_and_what_to_do_when_nothing_can_be_pasted(self):
        from heyphony.src.setup import routes
        for name in routes.ROUTES:
            hook = routes.hook(name, "https://host:8099")
            self.assertIn(hook["kind"], ("email", "webhook-json", "url-forward", "post-to-url", "xmpp", "none"))
            self.assertIn("evidence", hook)
            self.assertFalse(hook["verified"])
            if hook["kind"] in ("none", "xmpp", "email"):
                self.assertIsNone(hook["paste_url"], name)
            else:
                self.assertTrue(hook["paste_url"].startswith("https://host:8099/sms/"), name)
        anveo = routes.hook("anveo", "https://host:8099")["paste_url"]
        self.assertIn("$[from]$", anveo)
        self.assertIn("$[message]$", anveo)

    def test_bulkvs_registers_one_webhook_over_its_api_and_needs_credentials_first(self):
        from heyphony.src.setup import routes
        dry = routes.apply_hook("bulkvs", "https://host:8099")
        self.assertFalse(dry["applied"])
        self.assertEqual(sorted(dry["missing"]), ["BULKVS_API_PASS", "BULKVS_API_USER"])
        self.assertIn("https://host:8099/sms/bulkvs", dry["as_curl"])
        self.assertIn("webHooks", dry["as_curl"])
        self.assertIn('"Webhook": "comms"', dry["as_curl"])

    def test_one_envelope_out_of_five_more_shapes(self):
        from heyphony.src.setup import routes
        bulk = routes.normalize("bulkvs", {"From": "+1555", "To": "+1666", "Message": "yo", "RefId": "r1"})
        self.assertEqual((bulk["sender"], bulk["recipient"], bulk["body"], bulk["id"]), ("+1555", "+1666", "yo", "r1"))
        questblue = routes.normalize("questblue", {"from": "+1555", "to": "+1666", "msg": "hey"})
        self.assertEqual(questblue["body"], "hey")
        signalwire = routes.normalize("signalwire", {"message": {"from": "+1", "to": "+2", "body": "hi", "message_id": "m1"}})
        self.assertEqual(signalwire["id"], "m1")
        anveo = routes.normalize("anveo", {"from": "+1", "to": "+2", "message": "hello"})
        self.assertTrue(anveo["id"].startswith("anveo:"))
        # a provider that posts nothing still cannot crash the catcher
        self.assertEqual(routes.normalize("voyced", {"surprise": True})["id"], "voyced:unexpected")
        self.assertEqual(routes.normalize("jmp.chat", {"surprise": True})["id"], "jmp.chat:unexpected")
        with self.assertRaises(KeyError):
            routes.normalize("twilio", {})

    def test_an_unknown_rail_is_refused(self):
        code, text = self.run_cli(["setup", "select", "carrier-pigeon"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(text)["rails"], ["sip"])

    def test_the_old_plan_flag_still_prints_the_plan(self):
        code, text = self.run_cli(["setup"])
        self.assertEqual(code, 0)
        self.assertIn("lanes", json.loads(text))


class _FakeTransport:
    """stands in for the socket, so the driver is proven without baresip installed anywhere."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.sent = []
        self.closed = False

    def send(self, message):
        self.sent.append(message)
        return message

    def recv(self, timeout=None):
        if not self.steps:
            self.closed = True
            return []
        step = self.steps.pop(0)
        return step(self) if callable(step) else step

    def close(self):
        self.closed = True


def _response(ok=True, data=""):
    def step(fake):
        return [{"response": True, "ok": ok, "data": data, "token": fake.sent[-1]["token"]}]
    return step


def _events(*types, param=None):
    return [{"event": "true", "class": "call", "type": name, "param": param} for name in types]


class TestTheTaskShape(unittest.TestCase):
    """the part a hosted tool genuinely did better, implemented here against our own client."""

    def setUp(self):
        from callheavy.src import task
        self.t = task
        self.schema = {"type": "object", "additionalProperties": False,
                       "required": ["tuesday_confirmed"],
                       "properties": {"tuesday_confirmed": {"type": "string",
                                                           "enum": ["yes", "no", "unknown"],
                                                           "description": "yes when tuesday is held"},
                                      "callback_needed": {"type": "boolean"}}}

    def test_a_task_says_a_goal_and_the_fields_to_bring_back(self):
        item = self.t.task("confirm the tuesday cleaning", self.schema, "a yes or a no")
        self.assertEqual(item["goal"], "confirm the tuesday cleaning")
        self.assertEqual(item["must_collect"], self.schema)
        self.assertEqual(item["success"], "a yes or a no")

    def test_an_underdescribed_task_is_told_exactly_what_is_missing(self):
        missing = self.t.clarifications(self.t.task(""), None)
        self.assertEqual([entry["needs"] for entry in missing],
                         ["goal", "phone", "must_collect", "success"])
        for entry in missing:
            self.assertIn("flag", entry)
            self.assertIn("why", entry)
        self.assertEqual(self.t.clarifications(self.t.task("ask about lunch", self.schema, "a yes"), "+1555"), [])

    def test_an_unsupported_schema_feature_is_refused_before_the_call(self):
        schema = {"type": "object", "properties": {"when": {"oneOf": [{"type": "string"}]}}}
        problems = self.t.schema_problems(schema)
        self.assertEqual(problems[0]["unsupported"], "oneOf")
        self.assertIn("before", "before the call")
        self.assertEqual(self.t.schema_problems({"type": "string"})[0]["unsupported"], "root")

    def test_the_validator_accepts_a_good_answer_and_names_a_bad_one(self):
        self.assertEqual(self.t.validate({"tuesday_confirmed": "yes", "callback_needed": False}, self.schema), [])
        problems = self.t.validate({"tuesday_confirmed": "maybe", "callback_needed": "yes",
                                    "invented": 1}, self.schema)
        seen = {(entry["path"], entry["problem"]) for entry in problems}
        self.assertIn(("$.tuesday_confirmed", "enum"), seen)
        self.assertIn(("$.callback_needed", "type"), seen)
        self.assertIn(("$.invented", "additional"), seen)
        self.assertIn(("$.tuesday_confirmed", "required"),
                      {(entry["path"], entry["problem"]) for entry in self.t.validate({}, self.schema)})

    def test_nested_fields_are_validated_where_they_are(self):
        schema = {"type": "object", "properties": {"slots": {"type": "array", "items": {
            "type": "object", "required": ["day"], "properties": {"day": {"type": "string"}}}}}}
        problems = self.t.validate({"slots": [{"day": "tuesday"}, {}]}, schema)
        self.assertEqual([(p["path"], p["problem"]) for p in problems], [("$.slots[1].day", "required")])

    def test_a_bool_is_not_an_integer_and_an_int_is_not_a_bool(self):
        self.assertTrue(self.t.validate(True, {"type": "integer"}))
        self.assertTrue(self.t.validate(1, {"type": "boolean"}))

    def test_the_envelope_has_four_states_and_only_one_of_them_is_an_answer(self):
        good = self.t.envelope({"tuesday_confirmed": "yes"}, self.schema, transcript=[{"speaker": "bot"}],
                               outcome="completed")
        self.assertEqual(good["result_status"], "available")
        self.assertIsNone(good["error"])
        self.assertEqual(good["call_outcome"], "completed")

        invalid = self.t.envelope({"tuesday_confirmed": "maybe"}, self.schema)
        self.assertEqual(invalid["result_status"], "unavailable")
        self.assertEqual(invalid["error"]["code"], "result_invalid")
        self.assertIsNone(invalid["result"], "an invalid answer is not handed on as an answer")

        absent = self.t.envelope(None, self.schema)
        self.assertEqual(absent["error"]["code"], "result_failed")

        broken = self.t.envelope(None, self.schema, error="call_failed", outcome="busy")
        self.assertEqual(broken["result_status"], "not_applicable")
        self.assertEqual(broken["call_outcome"], "busy")

    def test_an_invented_call_outcome_is_dropped_rather_than_passed_on(self):
        self.assertIsNone(self.t.envelope(None, None, outcome="vibes")["call_outcome"])

    def test_the_prompt_is_text_a_person_can_read_and_a_test_can_pin(self):
        item = self.t.task("confirm the tuesday cleaning", self.schema, "a yes or a no")
        prompt = self.t.extract_prompt(item, [{"offset": 0, "speaker": "bot", "text": "hello"},
                                             {"offset": 3, "speaker": "user", "text": "tuesday is fine"}])
        self.assertIn("confirm the tuesday cleaning", prompt)
        self.assertIn("tuesday_confirmed", prompt)
        self.assertIn("yes when tuesday is held", prompt)
        self.assertIn("unknown", prompt)
        self.assertIn("reply with one json object", prompt)
        self.assertIn("[3] user: tuesday is fine", prompt)
        self.assertNotIn("openai", prompt.lower())
        self.assertNotIn("api", prompt.lower())


class TestTheHostConfig(unittest.TestCase):
    """the two lines that decide whether a socket can do anything at all."""

    def setUp(self):
        from callheavy.src import host
        self.host = host

    def test_the_config_loads_the_modules_a_dial_needs(self):
        text = self.host.config_text("linux")
        modules = self.host.loaded_modules(text)
        for needed in ("menu.so", "ctrl_tcp.so", "alsa.so", "g711.so", "account.so"):
            self.assertIn(needed, modules, f"the config does not load {needed}")

    def test_the_control_socket_listens_on_loopback_and_not_on_the_wifi(self):
        text = self.host.config_text("linux")
        self.assertIn("ctrl_tcp_listen\t\t127.0.0.1:4444", text)
        self.assertNotIn("0.0.0.0:4444", text)

    def test_every_host_row_names_its_audio_driver_and_admits_what_is_unverified(self):
        linux = self.host.host_row("linux")
        macos = self.host.host_row("macos")
        self.assertTrue(linux["verified"], "the linux row is the one that has been run here")
        self.assertFalse(macos["verified"], "the mac row is not verified and says so in its own data")
        self.assertIn("coreaudio", macos["device"])
        self.assertIn("coreaudio.so", self.host.config_text("macos"))

    def test_the_accounts_line_is_refused_when_the_host_is_a_sentence(self):
        with self.assertRaises(ValueError):
            self.host.accounts_text("+15551234567", "u", "p", "regional: atlanta, chicago")
        line = self.host.accounts_text("+15551234567", "u", "p", "atlanta.voip.ms")
        self.assertIn("<sip:u@atlanta.voip.ms>", line)
        self.assertIn("auth_pass=p", line)
        self.assertIn('"+15551234567"', line)

    def test_both_files_are_written_0600_and_a_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as home:
            dry = self.host.write("+15551234567", "u", "p", "atlanta.voip.ms", home=home, dry=True)
            self.assertTrue(dry["dry"])
            self.assertFalse((pathlib.Path(home) / "config").exists(), "a dry run wrote a file")
            written = self.host.write("+15551234567", "u", "p", "atlanta.voip.ms", home=home)
            for key in ("config", "accounts"):
                mode = os.stat(written["paths"][key]).st_mode & 0o777
                self.assertEqual(mode, 0o600, f"{key} holds a password or a secret and is not 0600")
            self.assertEqual(len(list(pathlib.Path(home).glob("*"))), 2)


class TestTheSocketProtocol(unittest.TestCase):
    """spoken the way ctrl_tcp's own source documents it, including where it contradicts itself."""

    def setUp(self):
        from callheavy.src import dial
        self.dial = dial

    def test_a_command_is_a_string_params_and_a_token(self):
        message = self.dial.command("dial", "sip:+15551234567")
        self.assertEqual(message["command"], "dial")
        self.assertIsInstance(message["params"], str)
        self.assertIn("token", message)

    def test_a_netstring_round_trips(self):
        wire = self.dial.encode({"command": "dial", "params": "sip:alice@atlanta.com"})
        self.assertTrue(wire[:1].isdigit(), "a netstring starts with its length")
        self.assertTrue(wire.endswith(b","))
        messages, rest = self.dial.decode(wire)
        self.assertEqual(messages, [{"command": "dial", "params": "sip:alice@atlanta.com"}])
        self.assertEqual(rest, b"")

    def test_two_messages_in_one_read_both_come_out_and_a_partial_one_waits(self):
        first = self.dial.encode({"response": True, "ok": True})
        second = self.dial.encode({"event": "true", "type": "CALL_RINGING"})
        messages, rest = self.dial.decode(first + second + b"12:{\"event\"")
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[1]["type"], "CALL_RINGING")
        self.assertTrue(rest.startswith(b"12:"), "the incomplete tail is kept for the next read")

    def test_a_bare_json_message_parses_too(self):
        messages, rest = self.dial.decode(b'{"response": true, "ok": true}')
        self.assertEqual(messages, [{"response": True, "ok": True}])
        self.assertEqual(rest, b"")

    def test_the_modules_own_examples_are_the_contract(self):
        response = {"response": True, "ok": True, "data": "", "token": "qwerasdf"}
        event = {"event": "true", "class": "call", "type": "CALL_CLOSED", "param": "Connection reset",
                 "accountaor": "sip:alice@atlanta.com", "direction": "incoming",
                 "peeruri": "sip:bob@biloxy.com", "id": "73a12546589651f8"}
        self.assertEqual(self.dial.classify(response)[0], "response")
        self.assertEqual(self.dial.classify(event)[0], "event")
        self.assertEqual(self.dial.classify({"event": True, "type": "CALL_RINGING"})[0], "event")
        self.assertEqual(self.dial.classify({"nonsense": 1})[0], "noise")

    def test_a_call_is_reported_as_four_separate_facts(self):
        fake = _FakeTransport([_response(True), _events("CALL_RINGING"), _events("CALL_ESTABLISHED"),
                               _events("CALL_CLOSED", param="normal clearing")])
        result = self.dial.dial("sip:+15551234567", transport=fake, settle=5)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["stopped"], "closed")
        self.assertIsNotNone(result["ringing"])
        self.assertIsNotNone(result["established"])
        self.assertEqual(result["call_outcome"], "completed")
        self.assertIn("carrier", result["note"])

    def test_a_call_nobody_answered_is_not_reported_as_a_failure(self):
        fake = _FakeTransport([_response(True), _events("CALL_RINGING"),
                               _events("CALL_CLOSED", param="Request Timeout")])
        result = self.dial.dial("sip:+15551234567", transport=fake, settle=5)
        self.assertIsNone(result["established"])
        self.assertEqual(result["call_outcome"], "no_answer")

    def test_a_refused_dial_is_a_refusal_and_not_a_call(self):
        fake = _FakeTransport([_response(False, data="command not found")])
        result = self.dial.dial("sip:+15551234567", transport=fake, settle=5)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["stopped"], "refused")
        self.assertIn("command not found", result["error"])

    def test_a_deadline_says_deadline_and_does_not_hang(self):
        class Silent(_FakeTransport):
            """accepts the dial, then never says anything and never hangs up: the ringing phone."""
            def recv(self, timeout=None):
                return [] if self.sent else None

        fake = Silent([_response(True)])
        started = time.monotonic()
        result = self.dial.dial("sip:+15551234567", transport=fake, settle=0.4)
        self.assertEqual(result["stopped"], "deadline")
        self.assertLess(time.monotonic() - started, 5, "the driver overran its own deadline")

    def test_no_socket_names_the_module_instead_of_raising(self):
        class Broken:
            closed = False
            def send(self, message):
                raise OSError("connection refused")
            def close(self):
                pass
        result = self.dial.dial("sip:+15551234567", transport=Broken(), settle=1)
        self.assertEqual(result["stopped"], "no-socket")
        self.assertIn("ctrl_tcp", result["why"])
        self.assertIn("baresip", result["why"])


class TestTheAudioRails(unittest.TestCase):
    """where the agent's voice enters, and the one link that is not free."""

    def setUp(self):
        from callheavy.src import audio
        self.audio = audio

    def test_linux_gets_a_virtual_mic_from_pactl(self):
        row = self.audio.virtual_mic("linux")
        self.assertEqual(len(row["commands"]), 2)
        self.assertIn("module-null-sink", row["commands"][0])
        self.assertIn("module-remap-source", row["commands"][1])
        self.assertEqual(row["client_device"], "agent-mic")
        self.assertTrue(row["oss"])
        self.assertTrue(row["verified"])

    def test_macos_names_the_reboot_and_windows_names_the_non_oss_link(self):
        macos = self.audio.virtual_mic("macos")
        self.assertEqual(macos["commands"], [], "blackhole is an install, not a command")
        self.assertIn("GPL-3.0", macos["license"])
        self.assertFalse(macos["verified"])
        windows = self.audio.virtual_mic("windows")
        self.assertFalse(windows["oss"])
        self.assertIn("NOT oss", windows["license"])

    def test_a_wav_can_be_a_browser_microphone(self):
        flags = self.audio.browser_mic("/tmp/voice.wav")["args"]
        self.assertTrue(any("--use-fake-device-for-media-stream" in flag for flag in flags))
        self.assertTrue(any("/tmp/voice.wav" in flag for flag in flags))

    def test_the_room_gate_is_closed_until_all_three_names_exist(self):
        saved = {name: os.environ.pop(name, None) for name in self.audio.LIVEKIT_ENV}
        try:
            state = self.audio.room_state()
            self.assertTrue(state["closed"])
            self.assertEqual(sorted(state["missing"]), sorted(self.audio.LIVEKIT_ENV))
            refuse = self.audio.publish()
            self.assertFalse(refuse["ok"])
            self.assertEqual(sorted(refuse["missing"]), sorted(self.audio.LIVEKIT_ENV))
            os.environ["LIVEKIT_URL"] = "wss://example.invalid"
            self.assertIn("LIVEKIT_API_KEY", self.audio.room_state()["missing"])
        finally:
            for name, value in saved.items():
                os.environ.pop(name, None)
                if value is not None:
                    os.environ[name] = value

    def test_a_publish_without_the_sdk_names_the_install_line(self):
        saved = {name: os.environ.get(name) for name in self.audio.LIVEKIT_ENV}
        for name in self.audio.LIVEKIT_ENV:
            os.environ[name] = "set-for-this-test"
        try:
            answer = self.audio.publish()
        finally:
            for name, value in saved.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        if answer["ok"]:
            self.skipTest("the livekit sdk happens to be installed on this machine")
        self.assertEqual(answer["missing"], ["livekit"])
        self.assertIn("pip install livekit", answer["install"])

    def test_the_bridge_is_named_as_not_shipped(self):
        plan = self.audio.bridge_plan()
        self.assertFalse(plan["shipped"])
        self.assertIn("participant", plan["what_it_would_be"])
        self.assertIn("not a helper", plan["why_not_shipped"])
        self.assertEqual(self.audio.readiness("linux")["bridge"], "not shipped")


class TestTheCallHeavyCli(unittest.TestCase):
    def setUp(self):
        from callheavy.src import cli
        self.cli = cli

    def run_cli(self, argv):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = self.cli.main(argv)
        return code, json.loads(buffer.getvalue())

    def test_a_dial_is_a_plan_until_run_and_needs_a_named_authoriser(self):
        with tempfile.TemporaryDirectory() as room:
            schema = pathlib.Path(room) / "want.json"
            schema.write_text(json.dumps({"type": "object", "required": ["ok"],
                                          "properties": {"ok": {"type": "string"}}}))
            code, plan = self.run_cli(["dial", "--goal", "ask about tuesday", "--to", "+15551234567",
                                       "--schema", str(schema), "--success", "a yes"])
            self.assertEqual(code, 1)
            self.assertEqual(plan["problems"][0]["needs"], "authorized")

            code, plan = self.run_cli(["dial", "--goal", "ask about tuesday", "--to", "+15551234567",
                                       "--schema", str(schema), "--success", "a yes",
                                       "--authorized", "filmosophy"])
            self.assertEqual(code, 0)
            self.assertFalse(plan["sending"], "a dial without --run must not dial")
            self.assertEqual(plan["dial"], "sip:+15551234567")

    def test_a_plan_with_no_schema_is_refused_with_the_flag_to_fix(self):
        code, answer = self.run_cli(["plan", "--goal", "ask about tuesday", "--to", "+15551234567"])
        self.assertEqual(code, 1)
        self.assertEqual(answer["problems"][0]["flag"], "--schema")


class TestTheCallHeavyPage(unittest.TestCase):
    page = ROOT / "callheavy" / "readme.md"

    def test_the_page_is_our_own_calls_and_not_a_hosted_rail(self):
        text = self.page.read_text()
        self.assertIn("our own stack", text)
        self.assertIn("their dialler is not in this path", text)
        self.assertIn("no hosted dialler", text)
        self.assertNotIn("CALLE_API_KEY", text)

    def test_the_page_keeps_the_credit_and_the_distinction(self):
        text = self.page.read_text()
        self.assertIn("call-e", text)
        self.assertIn("MIT", text)
        self.assertIn("borrowed", text)

    def test_the_page_names_the_two_modules_and_the_loopback_bind(self):
        text = self.page.read_text()
        self.assertIn("commented out", text)
        self.assertIn("menu.so", text)
        self.assertIn("loopback", text)
        self.assertIn("127.0.0.1:4444", text)

    def test_the_page_says_what_is_refused_and_what_is_unproven(self):
        text = self.page.read_text()
        for needle in ("no otp", "no lists", "no live call has been placed", "verified: false",
                       "not shipped"):
            self.assertIn(needle, text, f"the page lost {needle!r}")

    def test_the_page_has_no_em_dash(self):
        self.assertNotIn("\u2014", self.page.read_text())


class TestTheFoldInTouchesOnlyItsOwnFolder(unittest.TestCase):
    def test_the_package_is_edited_in_exactly_one_place(self):
        """a fold-in that starts rewriting the package is a merge problem wearing a feature's clothes."""
        git = shutil.which("git")
        if not git:
            self.skipTest("no git on this machine")
        done, base = None, None
        for candidate in ("main", "origin/main"):
            attempt = subprocess.run([git, "-C", str(ROOT), "diff", "--name-only", candidate,
                                      "--", "heyphony"], capture_output=True, text=True, timeout=60)
            if attempt.returncode == 0:
                done, base = attempt, candidate
                break
        if done is None:
            self.skipTest("no main or origin/main to compare against in this clone")
        self.assertIn(base, ("main", "origin/main"))
        changed = [line for line in done.stdout.split() if line]
        self.assertEqual(changed, ["heyphony/theidea/calling.md"],
                         f"the fold-in edited the package: {changed}")

    def test_the_lane_lives_outside_the_package(self):
        self.assertTrue((ROOT / "callheavy" / "src" / "dial.py").is_file())
        self.assertTrue((ROOT / "bin" / "callheavy").is_file())
        self.assertEqual(list((ROOT / "heyphony").rglob("dial.py")), [])

    def test_nothing_in_the_package_imports_the_lane(self):
        for path in sorted((ROOT / "heyphony").rglob("*.py")):
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")):
                    self.assertNotIn("callheavy", stripped, f"{path.name} imports the optional lane")

    def test_the_lane_imports_nothing_but_the_standard_library(self):
        allowed = {"argparse", "json", "os", "pathlib", "socket", "sys", "time", "uuid",
                   "callheavy", "livekit"}
        for path in sorted((ROOT / "callheavy").rglob("*.py")):
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")):
                    self.assertIn(stripped.split()[1].split(".")[0], allowed,
                                  f"{path.name} imports something outside the standard library")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    failed = len(result.failures) + len(result.errors)
    print(f"selftest: {result.testsRun - failed}/{result.testsRun} pass")
    sys.exit(1 if failed else 0)
