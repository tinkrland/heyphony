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

# this repo carries no .gitignore, so nothing here may leave __pycache__ behind
sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.runner import cli as telephony_cli
from src.manage import catcher as phone_catcher
from src.onramp import flow as getters
from src.manage import inbox
from src import providers
from src.setup import flow as setup_flow
from src.linphone import sip
from src.linphone import sip as linphone


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
        source = (ROOT / "src/setup/flow.py").read_text()
        self.assertNotIn("\nimport termios", source, "termios moved to the top level, so windows breaks")
        self.assertNotIn("\nimport tty", source)
        self.assertIn("import termios", source, "the interactive path lost its terminal handling")


class TestThePackageIsStandalone(unittest.TestCase):
    """the whole reason this repo exists: the package does not need the umbrella behind it."""

    def test_no_import_reaches_outside_the_package_or_the_standard_library(self):
        allowed = {"argparse", "base64", "email", "hashlib", "hmac", "http", "json", "os",
                   "contextlib", "math", "pathlib", "re", "shlex", "shutil", "sqlite3", "src",
                   "subprocess", "sys", "termios", "time", "tty", "urllib", "uuid", "xml"}
        for path in sorted((ROOT / "src").rglob("*.py")):
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if not stripped.startswith(("import ", "from ")):
                    continue
                if stripped.startswith(("from src", "import src")):
                    continue
                module = stripped.split()[1].split(".")[0]
                self.assertIn(module, allowed,
                              f"{path.relative_to(ROOT)} imports {module}, which is not in the package")

    def test_the_umbrella_is_not_named_in_an_import_anywhere(self):
        for path in sorted((ROOT / "src").rglob("*.py")):
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")):
                    self.assertNotIn("comms", stripped, f"{path.relative_to(ROOT)}: {stripped}")

    def test_one_version_number_for_the_code_and_the_package(self):
        import src
        manifest = json.loads((ROOT / "npm/package.json").read_text())
        self.assertEqual(manifest["version"], src.__version__,
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
        bundled = self.npm / "python"
        self.assertTrue((bundled / "src/runner/cli.py").is_file())
        self.assertEqual(list(bundled.rglob("__pycache__")), [], "a cached .pyc does not belong in a tarball")
        self.assertEqual((bundled / "src/__init__.py").read_text().count("__version__"),
                         (ROOT / "src/__init__.py").read_text().count("__version__"))

    def test_the_installed_shim_runs_the_bundled_code(self):
        node = self.node()
        subprocess.run([node, str(self.npm / "scripts/bundle.js"), "--strict"],
                       capture_output=True, text=True, timeout=120, check=True)
        version = subprocess.run([node, str(self.npm / "bin/heyphony.js"), "--version"],
                                 capture_output=True, text=True, timeout=120)
        self.assertEqual(version.returncode, 0, version.stderr)
        import src
        self.assertEqual(version.stdout.strip(), src.__version__)
        doctor = subprocess.run([node, str(self.npm / "bin/heyphony.js"), "doctor"],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        self.assertIn("host_client", json.loads(doctor.stdout))

    def test_the_shim_says_what_is_wrong_instead_of_crashing(self):
        """a shim that dies with a traceback on a python-less machine teaches nobody anything."""
        source = (self.npm / "bin/heyphony.js").read_text()
        for needle in ("ENOENT", "brew install python3", "HEYPHONY_PYTHON", "127"):
            self.assertIn(needle, source, f"the missing-interpreter path lost {needle!r}")

    def test_the_bundle_work_is_removed_rather_than_ignored(self):
        """there is no .gitignore on this branch, so the copy has to delete itself after a pack."""
        self.assertFalse((ROOT / ".gitignore").exists(), "main carries no ignore file by request")
        manifest = json.loads((self.npm / "package.json").read_text())
        self.assertEqual(manifest["scripts"]["postpack"], "node scripts/bundle.js --clean")
        done = subprocess.run([self.node(), str(self.npm / "scripts/bundle.js"), "--clean"],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse((self.npm / "python").exists(), "postpack left the generated tree behind")
        subprocess.run([self.node(), str(self.npm / "scripts/bundle.js"), "--strict"],
                       capture_output=True, text=True, timeout=120, check=True)

    def test_the_url_installer_checks_its_two_prerequisites_first(self):
        script = (self.npm / "install.sh").read_text()
        for needle in ("python3", "sys.version_info >= (3, 8)", "curl", "HEYPHONY_HOME",
                       "HEYPHONY_REF", "refs/heads", "refs/tags", "ln -sf"):
            self.assertIn(needle, script, f"install.sh lost {needle!r}")
        self.assertNotIn("sudo", script, "an install that needs root is a different product")

    def test_the_installed_layout_is_the_one_the_installer_claims(self):
        """the shim resolves ../python relative to itself, and the installer must preserve that."""
        shim = (self.npm / "bin/heyphony.js").read_text()
        self.assertIn('path.join(pythonTree, "src", "runner", "cli.py")', shim)
        self.assertIn('"-m", "src.runner.cli"', shim)
        self.assertIn('PYTHONDONTWRITEBYTECODE', shim, "the shim must not leave a __pycache__ in a tree "
                                                      "that has no .gitignore to hide it")


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
        self.assertIn("the package is on the npm registry", text,
                      "it is published, so the page says so and names the version")
        self.assertIn("heyphony@0.2.0", text)
        npm_page = self.npm_readme.read_text()
        self.assertIn("is on the npm registry", npm_page.lower(),
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
        self.assertIn("the setup guide in this repo", text,
                      "the three modes still need a pointer to where the instructions are")

    def test_no_page_picked_up_an_em_dash(self):
        for page in [self.root_readme, self.npm_readme, self.agents]:
            self.assertNotIn("\u2014", page.read_text(), f"{page.name} has an em dash")

    def test_the_package_page_admits_it_came_from_the_umbrella(self):
        """the prose names sibling lanes that live elsewhere, so the page has to say so."""
        text = (ROOT / "readme.md").read_text()
        self.assertIn("this repo is the standalone package", text)
        self.assertIn("spawnables/tree/comms", text)

    def test_the_main_page_carries_no_repo_map_and_no_branch_table(self):
        """the owner's call: the tree and the branch list are not the front page's job."""
        text = self.root_readme.read_text()
        self.assertNotIn("## the tree", text)
        self.assertNotIn("| branch | what it is for |", text)
        for gone in ("omnimeetings", "`comms`", "bin/heyphony  the shim"):
            self.assertNotIn(gone, text, f"the front page still carries {gone!r}")


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
        from src.runner import cli as telephony_cli
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
        text = pathlib.Path("src/onramp/readme.md").read_text()
        for needle in ("## signal, which is built", "## telegram, which is two rails",
                       "webhook", "botfather", "heyphony get telegram"):
            self.assertIn(needle, text, f"the onramp page lost {needle!r}")
        self.assertIn("telegram.json", str(list(pathlib.Path("src/onramp").glob("*.json"))))


class TestOpeningTheInboxes(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.home = tempfile.mkdtemp()
        from src.manage import inbox as store
        self.store = store
        self.path = pathlib.Path(self.home) / "telephony" / "inbox.jsonl"
        store.append({"id": "a1", "channel": "sms", "sender": "+1555",
                      "body": "your signal code is 123456", "at": 1700000000}, self.path)
        store.append({"id": "a2", "channel": "sms", "sender": "+1666", "body": "hello", "at": 1700000100}, self.path)

    def test_rows_are_numbered_and_previewed(self):
        from src.manage import views
        out = views.messages(home=self.home, path=self.path)
        self.assertEqual([r["n"] for r in out["rows"]], [1, 2])
        self.assertEqual(out["rows"][0]["from"], "+1666")
        self.assertTrue(out["rows"][0]["preview"])

    def test_the_unread_mark_is_ours_because_the_provider_does_not_track_it(self):
        from src.manage import views
        self.assertEqual(views.messages(home=self.home, path=self.path)["unread_total"], 2)
        views.messages(home=self.home, path=self.path, do_mark=[1])
        self.assertEqual(views.messages(home=self.home, path=self.path, unread=True)["count"], 1)

    def test_show_expands_exactly_one_body(self):
        from src.manage import views
        out = views.messages(home=self.home, path=self.path, show=2)
        self.assertIn("signal code", out["message"]["body"])

    def test_a_thread_filter_narrows_to_one_number(self):
        from src.manage import views
        out = views.messages(home=self.home, path=self.path, thread="+1555")
        self.assertEqual(out["count"], 1)

    def test_voicemail_reads_its_sidecar_and_never_invents_a_transcript(self):
        from src.manage import views
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
        from src.manage import views
        out = views.calls(home=self.home)
        self.assertEqual((out["count"], out["rows"]), (0, []))

    def test_open_is_one_command_for_all_three(self):
        from src.manage import views
        self.assertEqual(views.messages(home=self.home, path=self.path)["inbox"], "messages")
        self.assertEqual(views.calls(home=self.home)["inbox"], "calls")
        self.assertEqual(views.voicemail(home=self.home)["inbox"], "voicemail")


class TestTheDirectoryExplainsItself(unittest.TestCase):
    """the complaint that started this: python files, no way to see how the thing runs."""

    root = pathlib.Path(__file__).resolve().parent.parent
    hey = root

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
        from src import providers
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
        from src.runner import cli
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
        from src.manage import catcher
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
        from src.setup import provision
        row = provision._area_row({"AREA_ID": "191.195.165.31.230", "AREA_CODE": "256",
                                   "AREA_NAME": "ALBERTVILLE", "STOCK": "49",
                                   "rate_plans": [{"RATE_PLAN_ID": "SU", "RATE_PLAN_NAME": "Service Unlimited",
                                                   "MONTHLY100": "149", "SETUP100": "249"}]})
        self.assertEqual((row["area_code"], row["stock"]), ("256", 49))
        self.assertEqual(row["rate_plans"][0]["monthly_usd"], 1.49)
        self.assertEqual(row["rate_plans"][0]["setup_usd"], 2.49)

    def test_apply_asks_for_stock_and_stops_at_the_order(self):
        from src.setup import provision
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
        from src.setup import provision
        parked = provision.plan("212", purchase=True)
        self.assertFalse(parked["ok"])
        self.assertEqual(parked["purchase"], "parked")
        self.assertIn("payment rail", parked["why"])
        self.assertIn("hooks anveo --apply", parked["instead"])

    def test_area_selection_is_first_class(self):
        from src.setup import provision
        self.assertEqual(sorted(provision.DID_TYPES), ["GEOGRAPHIC", "MOBILE", "NATIONAL", "TOLLFREE"])
        plan = provision.plan("212", area_name="new york", country_id="US")
        self.assertEqual(plan["area_name"], "new york")
        self.assertIn("param[COUNTRY_ID]=US", urllib.parse.unquote(plan["steps"][0]["as_curl"]))


class TestTheSetupPlanCoversVoicemailAndCatching(unittest.TestCase):
    def test_a_connect_line_is_not_the_whole_errand(self):
        from src.setup import flow as flow
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
        from src.runner import gui as launcher
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
        from src.runner import gui as launcher
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
        from src.runner import gui as launcher
        answer = launcher.draft("+15551230000", "sure, 3 works", path=self.inbox)
        self.assertFalse(answer["applied"])
        self.assertEqual(answer["provider"], "voip.ms")
        self.assertFalse(answer["outbound"]["now"])
        self.assertIn("no outbound api path", answer["outbound"]["why"])
        self.assertIn("draft", answer["note"])

    def test_voicemail_rows_carry_a_time_a_person_can_read(self):
        from src.runner import gui as launcher
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
        from src.runner import cli as telephony_cli
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
        from src.runner import gui as launcher
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
        from src.manage import mailparse
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
        from src.setup import provision
        self.assertEqual(provision.signature("some@email.com", "my secure phrase"),
                         "396cdfaff3491f457b95e51a5ebd89ad516d623d")

    def test_anveo_answers_parse_into_areas_and_numbers(self):
        from src.setup import provision
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
        from src.setup import provision
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
        from src.setup import flow as flow
        anveo = flow.plan_sip("anveo", "+12125551234")
        self.assertEqual(anveo["provisioning"]["now"], "cli")
        self.assertIn("setup provision", anveo["provisioning"]["command"])
        self.assertEqual(anveo["provisioning"]["stops_before"], "DID.ORDER")
        self.assertFalse(anveo["provisioning"]["spends_money"])
        flowroute = flow.plan_sip("flowroute", "+12125551234")
        self.assertEqual(flowroute["provisioning"]["now"], "browser")

    def test_arming_anveos_sms_refuses_without_credentials_and_shows_the_call(self):
        from src.setup import provision
        from src.setup import routes
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
        from src.setup import routes
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
        from src.setup import routes
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
        from src.setup import routes
        dry = routes.apply_hook("bulkvs", "https://host:8099")
        self.assertFalse(dry["applied"])
        self.assertEqual(sorted(dry["missing"]), ["BULKVS_API_PASS", "BULKVS_API_USER"])
        self.assertIn("https://host:8099/sms/bulkvs", dry["as_curl"])
        self.assertIn("webHooks", dry["as_curl"])
        self.assertIn('"Webhook": "comms"', dry["as_curl"])

    def test_one_envelope_out_of_five_more_shapes(self):
        from src.setup import routes
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


class TestThePackageIsPublishable(unittest.TestCase):
    """what a registry publish needs, checked as data so the runbook cannot drift from the tree."""

    npm = ROOT / "npm"
    manifest = json.loads((ROOT / "npm" / "package.json").read_text())
    page = ROOT / "npm" / "publish.md"

    def test_the_manifest_carries_the_fields_a_registry_reads(self):
        self.assertEqual(self.manifest["license"], "SEE LICENSE IN LICENSE",
                         "a custom licence is named by pointer, not by an spdx id it does not have")
        self.assertIn("tinkrland", self.manifest["author"])
        self.assertEqual(self.manifest["scripts"]["prepublishOnly"], "npm test",
                         "a publish must run the suite, not hope")
        self.assertEqual(self.manifest["scripts"]["preflight"], "node scripts/preflight.js")
        self.assertNotIn("private", self.manifest)

    def test_the_licence_is_source_available_and_says_so_in_its_own_words(self):
        text = (ROOT / "LICENSE").read_text()
        self.assertTrue(text.startswith("heyphony source available license"))
        for needle in ("not an open source one", "business source licence 1.1",
                       "functional source licence", "elastic licence 2.0", "tinkrland",
                       "competing use", "change date", "change licence", "mit licence"):
            self.assertIn(needle, text, f"the licence lost {needle!r}")
        self.assertNotIn("Permission is hereby granted, free of charge",
                         text, "a permissive grant belongs to the change licence, not this one")

    def test_every_released_version_has_a_change_date_table(self):
        text = (ROOT / "LICENSE").read_text()
        version = json.loads((ROOT / "npm/package.json").read_text())["version"]
        self.assertIn(version, text, "the version being shipped is not dated in the licence")
        rows = [line for line in text.splitlines() if line.strip().startswith(version)]
        self.assertTrue(rows, "no change date row for the shipped version")
        self.assertIn("MIT", rows[0])

    def test_the_licence_is_copied_beside_the_package_rather_than_duplicated_in_git(self):
        bundle = (self.npm / "scripts" / "bundle.js").read_text()
        self.assertIn("copyFileSync(licenceSource", bundle)
        self.assertIn('path.join(pkgDir, "LICENSE")', bundle)
        node = shutil.which("node")
        if not node:
            self.skipTest("no node on this machine")
        subprocess.run([node, str(self.npm / "scripts" / "bundle.js"), "--clean"],
                       capture_output=True, text=True, timeout=120, check=True)
        self.assertFalse((self.npm / "LICENSE").exists(),
                         "the copy is generated at pack time and cleaned by postpack")

    def test_the_maintainer_page_is_kept_out_of_the_tarball(self):
        files = self.manifest.get("files") or []
        self.assertNotIn("publish.md", files)
        self.assertNotIn("scripts/", files)
        self.assertIn("stays out of the tarball", self.page.read_text())

    def test_the_runbook_names_the_ceremony_and_the_permanent_parts(self):
        text = self.page.read_text()
        for needle in ("npm run preflight", "npm publish", "npm login --auth-type=web",
                       "granular access token", "72 hour", "npm deprecate", "--access public",
                       "cannot be reused", "npm/readme.md", "npx heyphony@latest"):
            self.assertIn(needle, text, f"the runbook lost {needle!r}")

    def test_the_preflight_checks_the_thing_that_actually_ships(self):
        script = (self.npm / "scripts" / "preflight.js").read_text()
        for needle in ('["pack"', '"install"', '"-g"', '"--prefix"', '"whoami"',
                       "registry.npmjs.org", "404", '"--version"', '"status"'):
            self.assertIn(needle, script, f"preflight stopped checking {needle!r}")
        self.assertIn("temp", script.lower(), "the install check must not touch the real prefix")

    def test_the_runbook_and_the_licence_have_no_em_dash(self):
        for page in (self.page, ROOT / "LICENSE"):
            self.assertNotIn("\u2014", page.read_text(), f"{page.name} has an em dash")


class TestTheMarketArgumentAndTheProviderIndex(unittest.TestCase):
    """the two pages that explain why the thing exists, rather than how to install it."""

    readme = ROOT / "readme.md"
    index = ROOT / "providers" / "readme.md"

    def test_the_readme_names_the_decoupled_offer_and_why_it_fails(self):
        text = self.readme.read_text()
        for needle in ("the market splits the number in half", "voice first", "text first",
                       "exposes the sip layer", "one number", "same number",
                       "read the call log and the message thread as one context"):
            self.assertIn(needle, text, f"the readme lost the market argument: {needle!r}")

    def test_the_readme_says_the_hybrid_is_the_reason_for_a_client(self):
        text = self.readme.read_text()
        self.assertIn("a client and a cli rather than a subscription", text)
        self.assertIn("charge you twice", text)

    def test_the_provider_index_starts_with_the_workflow_not_the_vendor(self):
        text = self.index.read_text()
        table = text.split("| how heavy the workflow is |")[1].split("\n\n")[0]
        for needle in ("heaviest", "heavy: receiving", "medium", "light", "none: codes"):
            self.assertIn(needle, table, f"the heaviness table lost the {needle!r} row")
        self.assertLess(text.index("how heavy the workflow is"), text.index("we are not affiliated"),
                        "the page must ask what the workflow does before it lists anybody")

    def test_the_provider_index_puts_the_messaging_app_case_in_the_uk_and_au(self):
        text = self.index.read_text()
        self.assertIn("virtual mobile number", text)
        self.assertIn("united kingdom (+44) or australia (+61)", text)
        self.assertIn("usa and canada mash cloud numbers", text)
        self.assertIn("cannot be registered in baresip or linphone", text)

    def test_the_provider_index_is_not_an_advertisement(self):
        text = self.index.read_text()
        for needle in ("we are not affiliated", "none of the vendors above pay for this",
                       "nothing here is a referral", "unverified until somebody pays",
                       "somebody else's computer"):
            self.assertIn(needle, text, f"the non affiliation section lost {needle!r}")
        self.assertNotIn("http", text.replace("https://github.com", ""), "no outbound vendor links")

    def test_the_provider_index_does_not_claim_experience_it_has_not_had(self):
        text = self.index.read_text().lower()
        self.assertIn("documentation is not experience", text)
        self.assertNotIn("we tested", text)


class TestTheInstalledCommandCanSayWhatItIs(unittest.TestCase):
    def test_version_is_answered_by_the_command_not_by_reading_the_file(self):
        done = subprocess.run([str(ROOT / "bin" / "heyphony"), "--version"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        import src
        self.assertEqual(done.stdout.strip(), src.__version__)
        self.assertIn('"--version", action="version"', (ROOT / "src/runner/cli.py").read_text(),
                      "argparse is what makes --version work with no terminal and no config")

    def test_the_installer_asks_the_command_it_installed(self):
        script = (ROOT / "npm/install.sh").read_text()
        self.assertIn('"$BIN_DIR/heyphony" --version', script,
                      "reading the version out of a file does not prove the shim runs")


class TestTheOutboundRail(unittest.TestCase):
    """sending exists now, and every reason it might not is a sentence rather than a stack trace."""

    def setUp(self):
        from src.manage.outgoing import send as outbox
        self.outbox = outbox
        self.saved = {k: os.environ.pop(k, None) for k in
                      ("HEYPHONY_SEND", "VOIPMS_API_USER", "VOIPMS_API_PASS", "FLOWROUTE_API_KEY",
                       "FLOWROUTE_API_SECRET", "SIGNALWIRE_SPACE", "SIGNALWIRE_PROJECT",
                       "SIGNALWIRE_TOKEN", "HEYPHONY_SIP_DID", "HEYPHONY_SIP_PROVIDER")}

    def tearDown(self):
        for name, value in self.saved.items():
            os.environ.pop(name, None)
            if value is not None:
                os.environ[name] = value

    def voipms(self):
        os.environ["VOIPMS_API_USER"] = "user"
        os.environ["VOIPMS_API_PASS"] = "secret"

    def test_a_body_costs_segments_and_says_which_encoding(self):
        self.assertEqual(self.outbox.segments("hello")["segments"], 1)
        self.assertEqual(self.outbox.segments("hello")["encoding"], "gsm7")
        split = self.outbox.segments("x" * 161)
        self.assertEqual((split["segments"], split["encoding"]), (2, "gsm7"))
        accented = self.outbox.segments("héllo")
        self.assertEqual((accented["encoding"], accented["bytes_max"]), ("ucs2", 70))
        self.assertEqual(self.outbox.segments("é" * 71)["segments"], 2)

    def test_one_recipient_means_one(self):
        self.assertTrue(self.outbox.one_recipient("+15551234567"))
        for bad in ("+15551234567,+15559998888", "+1 555 123 4567", "5551234567", "", None, "+12"):
            self.assertFalse(self.outbox.one_recipient(bad), bad)

    def test_each_provider_gets_the_request_its_docs_describe(self):
        self.voipms()
        request = self.outbox.request_for("voip.ms", "+15559990000", "+15551234567", "hi")
        self.assertEqual(request["method"], "GET")
        self.assertIn("method=sendSMS", request["url"])
        self.assertIn("did=%2B15559990000", request["url"])
        self.assertIn("dst=%2B15551234567", request["url"])

        os.environ["FLOWROUTE_API_KEY"] = "key"
        os.environ["FLOWROUTE_API_SECRET"] = "secret"
        flow = self.outbox.request_for("flowroute", "+15559990000", "+15551234567", "hi")
        self.assertEqual(flow["method"], "POST")
        self.assertEqual(flow["url"], "https://api.flowroute.com/v2.2/messages")
        self.assertTrue(flow["headers"]["Authorization"].startswith("Basic "))
        body = json.loads(flow["body"])
        self.assertEqual(body["data"]["type"], "message")
        self.assertEqual(body["data"]["attributes"]["body"], "hi")

        os.environ.update({"SIGNALWIRE_SPACE": "space", "SIGNALWIRE_PROJECT": "proj",
                           "SIGNALWIRE_TOKEN": "token"})
        sw = self.outbox.request_for("signalwire", "+15559990000", "+15551234567", "hi")
        self.assertIn("space.signalwire.com", sw["url"])
        self.assertIn("Accounts/proj/Messages.json", sw["url"])
        self.assertIn("Body=hi", sw["body"])

    def test_a_missing_credential_is_named_rather_than_half_configured(self):
        with self.assertRaises(ValueError) as caught:
            self.outbox.request_for("voip.ms", "+15559990000", "+15551234567", "hi")
        self.assertIn("VOIPMS_API_USER", str(caught.exception))

    def test_a_closed_gate_drafts_and_never_calls_out(self):
        self.voipms()
        calls = []

        def explode(request):
            calls.append(request)
            raise AssertionError("the rail sent with the gate closed")

        answer = self.outbox.send("voip.ms", "+15559990000", "+15551234567", "hi", allow=True,
                                  opener=explode)
        self.assertFalse(answer["sent"])
        self.assertTrue(answer["drafted"])
        self.assertIn("HEYPHONY_SEND", answer["why"])
        self.assertTrue(answer["curl"].startswith("curl "))
        self.assertNotIn("secret", answer["curl"], "a draft gets pasted; the password must not be in it")
        self.assertEqual(calls, [])

    def test_an_open_gate_still_needs_the_call_to_ask(self):
        self.voipms()
        os.environ["HEYPHONY_SEND"] = "allowed"
        answer = self.outbox.send("voip.ms", "+15559990000", "+15551234567", "hi", allow=False)
        self.assertFalse(answer["sent"])
        self.assertTrue(answer["drafted"])
        self.assertIn("did not ask", answer["why"])

    def test_a_send_records_both_halves_of_the_thread(self):
        self.voipms()
        os.environ["HEYPHONY_SEND"] = "allowed"
        seen = {}

        def accept(request):
            seen["request"] = request
            return 200, '{"status":"success"}'

        with tempfile.TemporaryDirectory() as room:
            path = pathlib.Path(room) / "inbox.jsonl"
            answer = self.outbox.send("voip.ms", "+15559990000", "+15551234567", "confirming tuesday",
                                      allow=True, path=path, opener=accept)
            self.assertTrue(answer["sent"], answer)
            self.assertTrue(answer["stored"])
            rows = inbox.read(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["direction"], "out")
            self.assertEqual(rows[0]["recipient"], "+15551234567")
            self.assertEqual(rows[0]["body"], "confirming tuesday")
        self.assertIn("sendSMS", seen["request"]["url"])

    def test_a_provider_that_cannot_send_names_the_ones_that_can(self):
        os.environ["HEYPHONY_SEND"] = "allowed"
        answer = self.outbox.send("anveo", "+15559990000", "+15551234567", "hi", allow=True)
        self.assertFalse(answer["sent"])
        self.assertEqual(answer["providers_with_a_send_path"],
                         ["flowroute", "signalwire", "voip.ms"])

    def test_a_list_and_a_wall_of_text_are_both_refused(self):
        self.voipms()
        os.environ["HEYPHONY_SEND"] = "allowed"
        listed = self.outbox.send("voip.ms", "+15559990000", "+15551234567,+15559998888", "hi",
                                  allow=True)
        self.assertFalse(listed["sent"])
        self.assertIn("one recipient", listed["why"])
        wall = self.outbox.send("voip.ms", "+15559990000", "+15551234567", "x" * 1601, allow=True)
        self.assertFalse(wall["sent"])
        self.assertIn("1600", wall["why"])
        empty = self.outbox.send("voip.ms", "+15559990000", "+15551234567", "   ", allow=True)
        self.assertFalse(empty["sent"])

    def test_a_rejected_send_says_what_the_provider_said(self):
        self.voipms()
        os.environ["HEYPHONY_SEND"] = "allowed"
        answer = self.outbox.send("voip.ms", "+15559990000", "+15551234567", "hi", allow=True,
                                  opener=lambda request: (400, '{"status":"invalid dst"}'))
        self.assertFalse(answer["sent"])
        self.assertEqual(answer["status"], 400)
        self.assertIn("invalid dst", answer["body"])

    def test_the_command_drafts_by_default_and_explains_a_missing_sender(self):
        from src.runner import cli as telephony_cli
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = telephony_cli.main(["send", "--to", "+15551234567", "--text", "hi"])
        self.assertEqual(code, 1)
        self.assertIn("HEYPHONY_SIP_DID", buffer.getvalue())

        self.voipms()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = telephony_cli.main(["send", "--to", "+15551234567", "--text", "hi",
                                       "--from", "+15559990000"])
        answer = json.loads(buffer.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(answer["sent"])
        self.assertTrue(answer["drafted"])


class TestWhatThePageRefusesToClaim(unittest.TestCase):
    """the owner's rule: no 2fa promise, and no pool whose reputation could be somebody else's."""

    readme = ROOT / "readme.md"
    outgoing = ROOT / "src/manage/outgoing/readme.md"

    def test_the_page_names_the_2fa_claim_it_is_declining_to_make(self):
        text = self.readme.read_text()
        for needle in ("the 2fa claim, which we are not making", "we do not promise a 2fa path",
                       "auto blocked", "banks and social media", "adversarial detection",
                       "sybil", "outright prohibition", "disparate impact",
                       "not a verdict on this package"):
            self.assertIn(needle, text, f"the page lost {needle!r}")

    def test_the_page_says_there_is_no_pool_and_no_shared_reputation(self):
        text = self.readme.read_text()
        for needle in ("we do not hold numbers in a pool", "no shared inventory",
                       "bought in your name from a provider you chose"):
            self.assertIn(needle, text, f"the pool claim lost {needle!r}")

    def test_the_page_no_longer_claims_outbound_never_leaves(self):
        text = self.readme.read_text()
        self.assertNotIn("outbound is a draft", text)
        self.assertIn("one message at a time", text)
        self.assertIn("HEYPHONY_SEND=allowed", text)
        self.assertIn("a campaign is a different product", text)

    def test_the_outgoing_page_states_the_same_rules_the_code_enforces(self):
        text = self.outgoing.read_text()
        for needle in ("HEYPHONY_SEND=allowed", "one recipient", "no half configuration",
                       "the terms are the operator's", "mms is refused", "verified: false",
                       "direction: \"out\""):
            self.assertIn(needle, text, f"the outgoing page lost {needle!r}")
        self.assertNotIn("today, nothing leaves", text, "the lane sends now, so say so")

    def test_neither_page_picked_up_an_em_dash_or_a_cloud_farm(self):
        for page in (self.readme, self.outgoing):
            text = page.read_text()
            self.assertNotIn("\u2014", text, f"{page.parent.name} has an em dash")
            self.assertNotIn("phone farm", text.lower())


class TestTheOutboundPathIndex(unittest.TestCase):
    """every provider the repo lists has an outbound answer, even when the answer is no."""

    def setUp(self):
        from src.manage.outgoing import send as outbox
        from src import providers
        self.out = outbox
        self.providers = providers

    def test_the_index_covers_every_provider_the_repo_knows(self):
        self.assertEqual(set(self.out.path_index()), set(self.providers.PROVIDERS),
                         "a provider in the table with no outbound row is the silent gap")

    def test_every_row_names_a_state_and_a_docs_link(self):
        for name, row in self.out.path_index().items():
            self.assertIn(row["state"], {"wired", "gateway not wired", "no http path",
                                         "no outbound sms claim"}, name)
            self.assertTrue(row["docs"].startswith("http"), f"{name} has no docs link")
            self.assertTrue(row["why"].strip(), f"{name} has no reason")

    def test_three_are_wired_and_the_rest_say_why_not(self):
        wired = sorted(n for n, r in self.out.path_index().items() if r["state"] == "wired")
        self.assertEqual(wired, ["flowroute", "signalwire", "voip.ms"])
        self.assertEqual(self.out.path_index()["jmp.chat"]["state"], "no http path")
        for name in ("anveo", "questblue", "bulkvs"):
            self.assertEqual(self.out.path_index()[name]["state"], "gateway not wired")
        for name in ("voyced", "voxacall", "bitcall"):
            self.assertEqual(self.out.path_index()[name]["state"], "no outbound sms claim")

    def test_a_refusal_carries_the_state_and_the_docs(self):
        answer = self.out.send("anveo", "+15551234567", "+15559998888", "hello")
        self.assertFalse(answer["sent"])
        self.assertEqual(answer["state"], "gateway not wired")
        self.assertIn("anveo.com", answer["docs"])
        self.assertIn("guessing them", answer["why"])

    def test_an_unknown_provider_is_named_as_unknown(self):
        answer = self.out.send("nonesuch", "+15551234567", "+15559998888", "hello")
        self.assertEqual(answer["state"], "unknown")
        self.assertFalse(answer["sent"])

    def test_the_cli_lists_the_paths(self):
        done = subprocess.run([str(ROOT / "bin" / "heyphony"), "send", "--paths"],
                              capture_output=True, text=True, timeout=90)
        self.assertEqual(done.returncode, 0, done.stderr)
        listed = json.loads(done.stdout)
        self.assertEqual(len(listed), len(self.providers.PROVIDERS))

    def test_the_page_names_the_software_it_owes_nothing_to(self):
        text = (ROOT / "providers/readme.md").read_text()
        for needle in ("belledonne communications sarl", "linphone", "baresip",
                       "not a partnership", "`heyphony send --paths`"):
            self.assertIn(needle, text, f"the affiliation section lost {needle!r}")



if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    failed = len(result.failures) + len(result.errors)
    print(f"selftest: {result.testsRun - failed}/{result.testsRun} pass")
    sys.exit(1 if failed else 0)
