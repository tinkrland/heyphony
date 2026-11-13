"""heyphony selftests: stdlib only. run: python3 tests/selftest.py

two kinds of test live here and they protect different things. the first kind pins behaviour,
using fixtures built from the schemas the code actually reads. the second kind pins prose: the
readme, the npm page and the agent page all make claims, and a claim that drifts from the code is
the specific failure mode of a package that has to be trusted with a phone number.
"""
import argparse
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer

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
                   "contextlib", "math", "pathlib", "re", "shlex", "shutil", "socket", "sqlite3", "src",
                   "subprocess", "sys", "termios", "threading", "time", "tty", "urllib", "uuid",
                   "xml"}
        import ast
        for path in sorted((ROOT / "src").rglob("*.py")):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [(node.module or "").split(".")[0]]
                else:
                    continue
                for module in names:
                    if module in ("src", ""):
                        continue
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
        self.assertEqual(list(manifest["bin"]), ["heyphony", "heyphony-mcp"])
        target = self.npm / manifest["bin"]["heyphony"]
        self.assertTrue(target.is_file(), "the bin entry points at nothing")
        self.assertTrue(os.access(target, os.X_OK), "the shim is not executable, so npm -g cannot link it")

    def test_the_files_list_ships_the_python_and_the_two_pages(self):
        manifest = json.loads((self.npm / "package.json").read_text())
        for entry in ("python/", "bin/", "readme.md", "agents.md"):
            self.assertIn(entry, manifest["files"], f"{entry} falls out of the tarball")
        self.assertIn("python3", (self.npm / "lib/python.js").read_text(),
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

    def test_the_npm_bundle_never_carries_the_pypi_build(self):
        """the bundler copies the repo root minus a skip list, so a new packaging folder is shipped by
        default unless it is skipped. pypi/ and its generated heyphony/ copy must not ride along."""
        node = self.node()
        pypi_build = ROOT / "pypi" / "build.py"
        subprocess.run([sys.executable, str(pypi_build)], capture_output=True, text=True, timeout=120, check=True)
        try:
            done = subprocess.run([node, str(self.npm / "scripts/bundle.js"), "--strict"],
                                  capture_output=True, text=True, timeout=120)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertFalse((self.npm / "python" / "pypi").exists(),
                             "the npm tarball would carry the pypi packaging folder")
            self.assertEqual(sorted(p.name for p in (self.npm / "python").iterdir() if p.name == "heyphony"), [])
        finally:
            subprocess.run([sys.executable, str(pypi_build), "--clean"], capture_output=True, text=True, timeout=120)
            subprocess.run([node, str(self.npm / "scripts/bundle.js"), "--clean"], capture_output=True, text=True, timeout=120)

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
        source = (self.npm / "lib/python.js").read_text()
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
        shim = (self.npm / "lib/python.js").read_text()
        self.assertIn('path.join(pythonTree, "src", "runner", "cli.py")', shim)
        self.assertIn('"-m", "src.runner.cli"', shim)
        self.assertIn('PYTHONDONTWRITEBYTECODE', shim, "the shim must not leave a __pycache__ in a tree "
                                                      "that has no .gitignore to hide it")


class TestThePagesSayHowToGetIt(unittest.TestCase):
    root_readme = ROOT / "readme.md"
    npm_readme = ROOT / "npm/readme.md"
    agents = ROOT / "npm/agents.md"

    def test_the_page_leads_with_the_registry_and_keeps_the_url_install_as_the_fallback(self):
        """the owner's order: npm first, the url install for a machine with neither git nor node."""
        text = " ".join(self.root_readme.read_text().split())
        npm_first = text.index("npm i -g heyphony")
        url_after = text.index("npm/install.sh")
        self.assertLess(npm_first, url_after, "the registry line has to come before the url install")
        self.assertIn("or, if you don't have either git nor node, the url install is a better fit", text)
        self.assertNotIn("git clone", text.split("## three places it can live")[0],
                         "the get it section no longer leads with a clone, so it does not list one")
        for needle in ("npx heyphony", "npm/readme.md", "npm/publish.md"):
            self.assertIn(needle, text, f"the root readme stopped pointing at {needle!r}")

    def test_the_page_lists_the_other_offerings_as_bullets(self):
        """the owner's shape: a short list under its own subheading, each line marked for how far along it is."""
        text = self.root_readme.read_text()
        self.assertIn("### other offerings", text)
        for needle in ("- mcp server (in development) @ `mcp` branch",
                       "- rest api over https (in development)",
                       "- heyphony sdk (planned)",
                       "- hosted cloud offering (paid only, planned)"):
            self.assertIn(needle, text, f"the offerings list lost {needle!r}")
        self.assertNotIn("does not pretend they are a fifth route", text,
                         "the paragraph this replaced is gone rather than sitting beside the list")

    def test_the_page_does_not_claim_a_publish_that_has_not_happened(self):
        text = self.root_readme.read_text()
        self.assertIn("the package is on the npm registry", text,
                      "it is published, so the page says so and names the version")
        import src
        self.assertIn(f"heyphony@{src.__version__}", text,
                      "the page names the version the code holds, not an older tag")
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
        self.assertIn("this is the standalone package", text)
        self.assertIn("spawnables/tree/comms", text)

    def test_the_opening_says_who_this_number_is_not_for(self):
        """the owner's call: the scope boundary belongs in the opening, where the pitch is."""
        text = (ROOT / "readme.md").read_text()
        opening = text.split("## telecom was built for people")[0]
        for needle in ("bulk outbound calling", "marketing campaigns", "a sales dialer",
                       "there are already enough companies selling it well"):
            self.assertIn(needle, opening, f"the opening stopped saying {needle!r}")
        self.assertNotIn("> **", opening,
                         "the stand-alone note was a blockquote in the opening; it is prose elsewhere now")

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
        for absent in ("heyphony call`",):
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

    def test_the_readme_states_the_two_new_volumes_and_their_honest_limits(self):
        text = self.readme.read_text()
        for needle in ("leaving a voicemail is the same act, with a voice",
                       "there is no answering-machine detection here",
                       "HEYPHONY_CALL=allowed"):
            self.assertIn(needle, text, f"the readme lost {needle!r}")

    def test_the_main_page_stays_quiet_about_groups_while_they_are_one_branchs_work(self):
        """the owner asked for the group chat portion to stay off this page; the command still exists
        and the command index still documents it."""
        page = (ROOT / "readme.md").read_text()
        # the tool surface below names real verbs, so the claim is pinned where it actually matters:
        # the page a stranger reads before it gets to the mcp section has no group chat claim on it
        above = page.split("### the same answers over mcp")[0].lower()
        self.assertNotIn("group", above, "the group chat portion was meant to come off the main page")
        self.assertIn("group", page.lower(), "the tool inventory still names the verbs the code has")
        self.assertIn("group", (ROOT / "src" / "setup" / "commands" / "readme.md").read_text().lower(),
                      "the command index is the reference, so it still documents the verb")

    def test_the_readme_states_what_a_lookup_can_and_cannot_say(self):
        text = self.readme.read_text()
        for needle in ("looking a number up is a read",
                       "never a boolean",
                       "carrier-question",
                       "the area code is assigned to a country, a territory or a region",
                       "`+1` is not the united states and canada"):
            self.assertIn(needle, text, f"the readme lost {needle!r}")

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
        self.assertIn("united kingdom", text)
        self.assertIn("+44", text)
        self.assertIn("share one bucket", text)
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


class TestEveryProviderHasAPage(unittest.TestCase):
    """the gap that prompted this: ten vendors in the data, two pages in the folder."""

    def providers_dir(self):
        return ROOT / "providers"

    def test_one_folder_per_provider_and_no_orphans(self):
        from src import providers
        folders = {p.name for p in self.providers_dir().iterdir()
                   if p.is_dir() and (p / "readme.md").is_file()}
        self.assertEqual(folders, set(providers.PROVIDERS),
                         "the vendor table and the folder must name the same ten")

    def test_every_page_says_how_texts_arrive_and_where_outbound_stands(self):
        from src.manage.outgoing import send
        for name, row in send.path_index().items():
            page = (self.providers_dir() / name / "readme.md").read_text().lower()
            self.assertIn("## outbound", page, f"{name} never says where sending stands")
            self.assertIn(row["state"], page,
                          f"{name} states {row['state']!r} in the code and not on its page")
            self.assertGreater(len(page), 900, f"{name} is a stub, not a page")

    def test_a_page_claims_nothing_verified(self):
        for path in sorted(self.providers_dir().glob("*/readme.md")):
            text = path.read_text().lower()
            for shot in ("verified:", '"verified": true', "proven to work today"):
                self.assertNotIn(shot, text, f"{path.parent.name} claims a proof it does not have")

    def test_no_page_calls_the_old_binary(self):
        """the two inherited pages said `telephony connect linphone`, which stopped existing."""
        for path in sorted(self.providers_dir().glob("*/readme.md")):
            text = path.read_text()
            self.assertNotIn("`telephony ", text, f"{path.parent.name} names the retired shim")
            self.assertNotIn("connect linphone", text, f"{path.parent.name} names the retired command")

    def test_the_index_links_every_page(self):
        from src import providers
        index = (self.providers_dir() / "readme.md").read_text()
        for name in providers.PROVIDERS:
            self.assertIn(f"({name}/readme.md)", index, f"the index does not link {name}")


class TestTheNumberingRanges(unittest.TestCase):
    """a country code is not a product. the uk range decides whether the text lane exists."""

    def setUp(self):
        from src.setup import numbering
        self.n = numbering

    def test_the_two_orderable_uk_ranges_are_named(self):
        answer = self.n.advice("GB")
        self.assertEqual(answer["orderable_prefixes"], ["07", "03"])
        self.assertIn("07 mobile", answer["order"])
        self.assertIn("01 and 02 are geographic landlines", answer["avoid"])
        self.assertEqual(answer["band"], "standard")

    def test_a_uk_mobile_range_reads_as_one(self):
        found = self.n.look("+447700900123")
        self.assertEqual(found["kind"], "mobile")
        self.assertEqual(found["sms"], "yes")
        self.assertTrue(found["orderable"])

    def test_a_uk_landline_is_the_same_order_form_and_the_wrong_product(self):
        for number in ("+442071234567", "+441614960000"):
            found = self.n.look(number)
            self.assertEqual(found["kind"], "geographic", number)
            self.assertEqual(found["sms"], "no")
            self.assertFalse(found["orderable"])
            warning = self.n.warn(number)
            self.assertIsNotNone(warning)
            self.assertIn("07 mobile", warning["next"])

    def test_personal_numbering_is_not_mistaken_for_a_mobile(self):
        """070 starts with 07 and behaves nothing like it, which is the trap in a prefix rule."""
        found = self.n.look("+447012345678")
        self.assertEqual(found["kind"], "personal numbering")
        self.assertEqual(found["sms"], "no")
        self.assertFalse(found["orderable"])

    def test_the_uk_voip_range_says_what_it_is(self):
        found = self.n.look("+445612345678")
        self.assertEqual(found["kind"], "voip")
        self.assertEqual(found["sms"], "no")
        self.assertIn("voip", found["why"])

    def test_a_good_number_gets_no_warning(self):
        self.assertIsNone(self.n.warn("+447700900123"))
        self.assertIsNone(self.n.warn("+443300000000"), "03 is usually text capable, not a refusal")

    def test_the_bands_are_the_owners_bands(self):
        standard = sorted(k for k, v in self.n.COUNTRIES.items() if v["band"] == self.n.STANDARD)
        pricier = sorted(k for k, v in self.n.COUNTRIES.items() if v["band"] == self.n.PRICIER)
        refused = sorted(k for k, v in self.n.COUNTRIES.items() if v["band"] == self.n.REFUSED)
        self.assertEqual(standard, ["GB", "LT", "PL", "SE"])
        self.assertEqual(pricier, ["AU", "NL"])
        self.assertEqual(refused, ["CA", "US"])

    def test_an_unknown_country_is_said_out_loud(self):
        answer = self.n.advice("JP")
        self.assertFalse(answer["known"])
        self.assertIn("no numbering opinion", answer["why"])

    def test_provisioning_prints_the_ranges_before_the_order(self):
        done = subprocess.run([str(ROOT / "bin" / "heyphony"), "setup", "provision",
                               "--numbering", "GB"], capture_output=True, text=True, timeout=90)
        self.assertEqual(done.returncode, 0, done.stderr)
        answer = json.loads(done.stdout)
        self.assertEqual(answer["numbering"]["band"], "standard")
        prefixes = [row["prefix"] for row in answer["ranges"]]
        self.assertIn("071", prefixes)
        self.assertIn("030", prefixes)
        self.assertNotIn("070", prefixes, "personal numbering is not an orderable range")

    def test_connect_sip_warns_about_a_did_that_cannot_be_texted(self):
        done = subprocess.run([str(ROOT / "bin" / "heyphony"), "connect", "sip", "--provider", "voip.ms",
                               "--did", "+442071234567", "--username", "u", "--password", "p"],
                              capture_output=True, text=True, timeout=90,
                              env={**os.environ, "HOME": tempfile.mkdtemp()})
        self.assertEqual(done.returncode, 0, done.stderr)
        answer = json.loads(done.stdout)
        self.assertEqual(answer["numbering"]["sms"], "no")
        self.assertIn("07 mobile", answer["warning"]["next"])

    def test_the_pages_and_the_data_agree(self):
        index = (ROOT / "providers/readme.md").read_text()
        table = index.split("| how heavy the workflow is |")[1].split("### why the region")[0]
        for iso, row in self.n.COUNTRIES.items():
            self.assertIn(row["name"], table, f"the table lost {row['name']}")
            self.assertIn(row["code"], table, f"the table lost {row['code']}")
        for band in (self.n.STANDARD, self.n.PRICIER):
            self.assertIn(band, table, f"the table lost the {band!r} band")
        loc = (ROOT / "theidea/locale.md").read_text()
        for needle in ("standard", "pricier", "07 and 03", "01 and 02", "056"):
            self.assertIn(needle, loc.lower(), f"locale.md lost {needle!r}")


class TestTheVersionOnThePagesMatchesTheCode(unittest.TestCase):
    """one number, everywhere: the code, the manifest, the install lines and the tags."""

    def test_both_pages_name_the_version_the_code_holds(self):
        import src
        for page in ("readme.md", "npm/readme.md"):
            text = (ROOT / page).read_text()
            named = set(re.findall(r"heyphony@(\d+\.\d+\.\d+)", text))
            named |= set(re.findall(r"heyphony-(\d+\.\d+\.\d+)\.tgz", text))
            self.assertTrue(named, f"{page} names no version at all")
            self.assertEqual(named, {src.__version__}, f"{page} names {named}, the code says {src.__version__}")

    def test_the_package_page_does_not_claim_the_first_publish_was_the_last(self):
        text = (ROOT / "npm/readme.md").read_text()
        self.assertNotIn("the first publish", text,
                         "that sentence only stays true until the second release")


class TestLeavingAVoicemail(unittest.TestCase):
    """one call, one person, and no answering-machine detection anywhere in the story."""

    def setUp(self):
        from src.manage.outgoing import voicemail
        self.v = voicemail
        self.msg = "sorry we missed each other, call me back when you get this"

    def test_a_call_needs_a_trunk_and_says_which_pieces_are_missing(self):
        plan = self.v.plan("+15551234567", self.msg, env={})
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["missing"], ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET",
                                          "LIVEKIT_SIP_TRUNK"])
        self.assertFalse(plan["honest"]["verified"])

    def test_the_missing_amd_check_is_stated_rather_than_hidden(self):
        self.assertIn("answering-machine-detection", self.v.REFUSES)
        plan = self.v.plan("+15551234567", self.msg, env={})
        self.assertIn("seconds after the call is answered", " ".join(plan["steps"]))
        self.assertEqual(plan["wait_after_answer"], 18)

    def test_one_recipient_and_nothing_long(self):
        problems = self.v.plan("+15551234567, +15551234568", self.msg, env={})["problems"]
        self.assertTrue(problems, "a list of numbers is not one call")
        self.assertIn("one recipient", problems[0]["why"].lower())
        long_one = self.v.plan("+15551234567", "word " * 400, env={})["problems"]
        self.assertTrue(any("too long to be a voicemail" == p["why"] for p in long_one))
        self.assertTrue(any("longer than a minute of speech" == p["why"] for p in long_one))

    def test_a_closed_gate_is_a_draft_and_names_the_gate(self):
        answer = self.v.leave("+15551234567", self.msg, allow=True, env={})
        self.assertFalse(answer["sent"])
        self.assertIn("HEYPHONY_CALL=allowed", answer["why"])

    def test_an_open_gate_with_no_trunk_refuses_and_names_the_piece(self):
        env = {"HEYPHONY_CALL": "allowed", "LIVEKIT_URL": "wss://x.livekit.cloud"}
        answer = self.v.leave("+15551234567", self.msg, allow=True, env=env)
        self.assertFalse(answer["sent"])
        self.assertIn("LIVEKIT_API_KEY", answer["why"])

    def test_the_dial_is_livekits_documented_sip_call(self):
        env = {"LIVEKIT_URL": "wss://proj.livekit.cloud", "LIVEKIT_SIP_TRUNK": "ST_abc"}
        request = self.v.dial_request(env, "+15551234567", "voicemail-123")
        self.assertEqual(request["url"], "https://proj.livekit.cloud/twirp/livekit.SIP/CreateSIPParticipant")
        self.assertEqual(request["body"]["sip_call_to"], "+15551234567")
        self.assertEqual(request["body"]["sip_trunk_id"], "ST_abc")
        self.assertTrue(request["body"]["wait_until_answered"])
        curl = self.v.as_curl(request)
        self.assertIn("$LIVEKIT_JWT", curl, "the curl line must not carry a secret")
        self.assertNotIn("Bearer <jwt", curl)

    def test_a_dialed_call_records_what_the_endpoint_answered(self):
        env = {"HEYPHONY_CALL": "allowed", "LIVEKIT_URL": "wss://p.livekit.cloud",
               "LIVEKIT_API_KEY": "k", "LIVEKIT_API_SECRET": "s", "LIVEKIT_SIP_TRUNK": "ST_1"}
        answer = self.v.leave("+15551234567", self.msg, allow=True, env=env,
                              opener=lambda request: {"ok": True, "status": 200})
        self.assertTrue(answer["sent"])
        self.assertIn("agent has to be running", answer["why"])

    def test_the_tts_worker_is_written_for_reading_not_hidden(self):
        script = self.v.agent_script("hello from the agent", wait=12)
        self.assertIn('MESSAGE = "hello from the agent"', script)
        self.assertIn("WAIT = 12", script)
        self.assertIn("no amd on this rail", script)


class TestAGroupIsNotAList(unittest.TestCase):
    """four named people are a conversation. the fifth makes it an audience."""

    def setUp(self):
        import tempfile
        from src.manage import groups
        self.g = groups
        self.store = tempfile.mktemp()
        self.members = [{"name": "ada", "number": "+15551230001"},
                        {"name": "bob", "number": "+15551230002"}]

    def tearDown(self):
        import os
        if os.path.exists(self.store):
            os.unlink(self.store)

    def test_two_named_people_make_a_group(self):
        answer = self.g.create("dinner plans", self.members, store=self.store)
        self.assertTrue(answer["ok"])
        self.assertTrue(answer["group"]["id"].startswith("dinner-plans-"))
        self.assertIn("one-to-one", answer["what_members_see"])

    def test_the_ceiling_is_four_and_it_is_not_a_flag(self):
        many = [{"name": f"p{i}", "number": f"+1555123000{i}"} for i in range(5)]
        answer = self.g.create("everyone", many, store=self.store)
        self.assertFalse(answer["ok"])
        self.assertEqual(self.g.MAX_MEMBERS, 4)
        self.assertTrue(any("audience" in p["why"] for p in answer["problems"]))

    def test_a_bare_number_is_not_a_member(self):
        answer = self.g.create("x", ["+15551230001", "+15551230002"], store=self.store)
        self.assertFalse(answer["ok"])
        self.assertIn("not a bare number", answer["problems"][0]["why"])

    def test_an_unnamed_member_and_a_duplicate_are_both_refused(self):
        answer = self.g.create("x", [{"name": "", "number": "+15551230001"},
                                     {"name": "bob", "number": "+15551230001"}],
                               store=self.store)
        self.assertFalse(answer["ok"])
        whys = " ".join(p["why"] for p in answer["problems"])
        self.assertIn("needs a name", whys)
        self.assertIn("same number twice", whys)

    def test_one_member_is_a_thread_not_a_group(self):
        answer = self.g.create("just us", [{"name": "ada", "number": "+15551230001"}],
                               store=self.store)
        self.assertFalse(answer["ok"])
        self.assertIn("one member is a thread", " ".join(p["why"] for p in answer["problems"]))

    def test_saying_something_drafts_to_every_member_and_records_the_attempt(self):
        created = self.g.create("dinner plans", self.members, store=self.store)
        answer = self.g.say(created["group"]["id"], "seven at the usual place", provider="voip.ms",
                            from_number="+15550001111", allow=False, store=self.store)
        self.assertEqual(answer["of"], 2)
        self.assertEqual(answer["sent"], 0)
        self.assertTrue(answer["draft"])
        self.assertIn("HEYPHONY_SEND=allowed", answer["why"])
        shown = self.g.show(created["group"]["id"], store=self.store)
        self.assertEqual(len(shown["group"]["messages"]), 1)
        self.assertEqual(shown["group"]["messages"][0]["of"], 2)

    def test_the_cli_creates_and_lists_a_group(self):
        env = {**os.environ, "HEYPHONY_GROUPS": self.store}
        done = subprocess.run([str(ROOT / "bin" / "heyphony"), "group", "new", "--name", "dinner plans",
                               "--with", "ada=+15551230001", "--with", "bob=+15551230002"],
                              capture_output=True, text=True, timeout=90, env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(json.loads(done.stdout)["ok"])
        listing = subprocess.run([str(ROOT / "bin" / "heyphony"), "group", "list"],
                                 capture_output=True, text=True, timeout=90, env=env)
        self.assertEqual(json.loads(listing.stdout)["count"], 1)


class TestTheToolSurface(unittest.TestCase):
    """the mcp server and the sdk: two adapters, no second implementation, and no gate they can close."""

    def setUp(self):
        self.npm = ROOT / "npm"
        self.pkg = json.loads((self.npm / "package.json").read_text())
        self.server = (self.npm / "bin" / "heyphony-mcp.js").read_text()

    def test_the_tarball_ships_two_bins_and_the_sdk_entry(self):
        self.assertEqual(self.pkg["bin"], {"heyphony": "bin/heyphony.js",
                                          "heyphony-mcp": "bin/heyphony-mcp.js"})
        self.assertEqual(self.pkg["main"], "index.js")
        self.assertEqual(self.pkg["exports"]["."], "./index.js")
        for needed in ("bin/", "lib/", "index.js", "python/"):
            self.assertIn(needed, self.pkg["files"])

    def test_the_server_has_no_dependencies_because_a_transport_is_not_a_tree(self):
        self.assertNotIn("dependencies", self.pkg)
        self.assertNotIn("devDependencies", self.pkg)
        requires = re.findall(r'require\("([^"]+)"\)', self.server)
        local = ("readline",)
        for name in requires:
            self.assertTrue(name.startswith(".") or name in local or name.startswith("node:"),
                            f"the server requires {name}, which would be a dependency")

    def test_the_python_discovery_lives_in_one_file_and_both_bins_use_it(self):
        for bin_name in ("heyphony.js", "heyphony-mcp.js"):
            text = (self.npm / "bin" / bin_name).read_text()
            self.assertIn('require("../lib/python")', text)
            self.assertNotIn("HEYPHONY_PYTHON", text, f"{bin_name} should not search for python itself")
        lib = (self.npm / "lib" / "python.js").read_text()
        self.assertIn("process.env.HEYPHONY_PYTHON", lib)

    def test_the_three_verbs_that_reach_outside_are_the_only_ones_flagged(self):
        spend = re.findall(r"gate: (SEND_GATE|CALL_GATE)", self.server)
        self.assertEqual(spend, ["SEND_GATE", "SEND_GATE", "CALL_GATE"])
        self.assertIn('const SEND_GATE = "HEYPHONY_SEND"', self.server)
        self.assertIn('const CALL_GATE = "HEYPHONY_CALL"', self.server)

    def test_a_shut_gate_is_reported_rather_than_retried_or_bypassed(self):
        self.assertIn("drafted: true", self.server)
        self.assertIn("nothing left this machine", self.server)
        self.assertNotIn("process.env.HEYPHONY_SEND = ", self.server)
        self.assertNotIn('"--apply"', self.server)
        self.assertNotIn('"--purchase"', self.server)

    def test_the_server_speaks_the_protocol_and_not_a_dialect(self):
        for method in ('"initialize"', '"tools/list"', '"tools/call"', '"ping"'):
            self.assertIn(f"if (method === {method})", self.server)
        self.assertIn("-32601", self.server)
        self.assertIn("-32700", self.server)
        self.assertIn("readline.createInterface({ input: process.stdin", self.server)

    def test_the_pages_carry_the_surface_and_the_gate_story(self):
        root = " ".join((ROOT / "readme.md").read_text().split())
        package = " ".join((self.npm / "readme.md").read_text().split())
        agents = " ".join((self.npm / "agents.md").read_text().split())
        self.assertIn("### the same answers over mcp, for an agent that is not a shell", root)
        self.assertIn("### the sdk is the cli with the parsing done", root)
        self.assertIn("### the tool surface cannot close a gate", root)
        self.assertIn("## as an mcp server", package)
        # the count in the heading is read off the server, so adding a tool without touching the page fails
        # here instead of leaving the prose quietly wrong
        server = (self.npm / "bin" / "heyphony-mcp.js").read_text()
        total = server.count('    name: "heyphony_')
        words = {12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen",
                 18: "eighteen", 19: "nineteen", 20: "twenty"}
        self.assertIn(total, words, "teach this test the word for the new count")
        self.assertIn(f"### {words[total]} tools, and which of them spend", package)
        spend = server.count("gate: SEND_GATE") + server.count("gate: CALL_GATE")
        self.assertEqual(spend, 3, "three tools reach outside the machine")
        self.assertIn(f"the other {words[total - spend]} only read", root)
        self.assertIn(f"{words[total - spend]} that read and three that reach outside the machine", agents)
        self.assertIn(f"{words[total - spend]} read: `heyphony_status`", package)
        self.assertIn("## if you speak mcp instead of a shell", agents)
        for page in (root, package, agents):
            self.assertIn("HEYPHONY_SEND=allowed", page)

    def test_the_pages_say_no_tool_edits_the_inbound_policy_and_the_code_agrees(self):
        server = (self.npm / "bin" / "heyphony-mcp.js").read_text()
        package = " ".join((self.npm / "readme.md").read_text().split())
        agents = " ".join((self.npm / "agents.md").read_text().split())
        names = re.findall(r'    name: "(heyphony_[a-z_]+)"', server)
        self.assertEqual(sorted(n for n in names if "allow" in n), ["heyphony_allow_check", "heyphony_allow_show"],
                         "an allow tool that edits would let a prompt open the agent's own door")
        for needle in ("there is no tool that edits it", "a refused sender comes back as an answer",
                       "an argument nobody declared"):
            self.assertIn(needle, package, f"the npm page lost {needle!r}")
        self.assertIn("there is no tool to change that policy: ask the human", agents)
        self.assertIn("function violations(tool, input)", server, "the schema is held, not just printed")
        self.assertIn("answers: [0, 1]", server, "a refused sender must not look like a crash")

    def test_the_suite_would_notice_a_server_that_stopped_answering(self):
        script = (self.npm / "scripts" / "test-mcp.js").read_text()
        self.assertIn('method: "initialize"', script)
        self.assertIn('method: "tools/list"', script)
        self.assertIn("gate.closed", script)
        self.assertIn("only the three verbs that reach outside this machine are marked as doing so", script)
        self.assertIn("test-mcp.js", self.pkg["scripts"]["test"])
        preflight = (self.npm / "scripts" / "preflight.js").read_text()
        self.assertIn('"heyphony-mcp"', preflight)
        self.assertIn('method: "tools/list"', preflight)

class TestTheLookupReadsThePlan(unittest.TestCase):
    """a number is classified by the plan that issues it, and unknown is a real answer."""

    def setUp(self):
        from src.lookup import classify
        self.c = classify

    def test_a_london_landline_is_a_landline_that_cannot_take_a_text(self):
        answer = self.c.classify("+442071234567")
        self.assertEqual(answer["type"], "landline")
        self.assertFalse(answer["receive_text"])
        self.assertEqual(answer["region"], "london")
        self.assertEqual(answer["market"], "GB")

    def test_a_uk_mobile_range_takes_a_text_and_a_056_range_does_not(self):
        mobile = self.c.classify("+447700900123")
        self.assertEqual(mobile["type"], "mobile")
        self.assertTrue(mobile["receive_text"])
        voip = self.c.classify("+445612345678")
        self.assertEqual(voip["type"], "voip")
        self.assertFalse(voip["receive_text"])

    def test_personal_numbering_is_not_a_mobile_even_though_it_starts_07(self):
        answer = self.c.classify("+447000123456")
        self.assertEqual(answer["type"], "personal numbering")
        self.assertFalse(answer["receive_text"])

    def test_a_north_american_number_comes_back_unknown_and_says_why(self):
        answer = self.c.classify("+15373832662")
        self.assertEqual(answer["market"], "US")
        self.assertEqual(answer["type"], "unknown")
        strengths = [row["strength"] for row in answer["evidence"]]
        self.assertEqual(strengths, [self.c.AREA_CODE, self.c.CARRIER_QUESTION],
                         "the area code is evidence of a place, the plan is evidence of nothing")
        self.assertFalse(answer["adapter"]["wired"], "the carrier adapter is named, not wired")

    def test_an_unseeded_market_is_named_rather_than_guessed(self):
        answer = self.c.classify("+33612345678")
        self.assertIsNone(answer["market"])
        self.assertEqual(answer["type"], "unknown")
        self.assertEqual(answer["evidence"][0]["strength"], self.c.UNSEEDED)

    def test_something_that_is_not_a_number_is_refused_before_classification(self):
        answer = self.c.classify("+99")
        self.assertFalse(answer["valid"])
        self.assertEqual(answer["type"], "unknown")
        self.assertEqual(answer["evidence"], [])

    def test_a_string_that_is_no_kind_of_input_is_refused_as_a_handle(self):
        answer = self.c.classify("still not an input")
        self.assertEqual(answer["kind"], "username")
        self.assertFalse(answer["valid"])
        self.assertFalse(answer["contactable_without_number"])
        self.assertIn("neither platform", answer["why"])

    def test_every_answer_carries_the_limits_it_cannot_cross(self):
        answer = self.c.classify("+447700900123")
        for key in ("porting", "person", "virtual", "carrier", "coverage"):
            self.assertIn(key, answer["limits"])
        self.assertFalse(answer["verified"])


class TestTheSupportMatrixIsEvidenceNotVerdict(unittest.TestCase):
    """no boolean per service, because a plan cannot produce one."""

    def setUp(self):
        from src.lookup import support
        self.s = support

    def test_a_mobile_is_possible_for_all_three_and_a_landline_is_unlikely(self):
        mobile = {r["service"]: r["verdict"] for r in self.s.support("+447700900123")["services"]}
        self.assertEqual(mobile["imessage"], self.s.POSSIBLE)
        self.assertEqual(mobile["whatsapp"], self.s.POSSIBLE)
        landline = {r["service"]: r["verdict"] for r in self.s.support("+442071234567")["services"]}
        self.assertEqual(landline["signal"], self.s.UNLIKELY)

    def test_no_verdict_is_ever_a_boolean(self):
        for number in ("+447700900123", "+442071234567", "+15373832662", "+33612345678"):
            for row in self.s.support(number)["services"]:
                self.assertIn(row["verdict"], (self.s.POSSIBLE, self.s.UNLIKELY, self.s.UNKNOWN),
                              f"{row['service']} returned {row['verdict']!r}")

    def test_plain_sms_is_the_only_line_the_plan_answers_outright(self):
        rows = {r["service"]: r for r in self.s.support("+447700900123")["services"]}
        self.assertEqual(rows["sms"]["basis"], "numbering plan")
        self.assertEqual(rows["whatsapp"]["basis"], "line class")
        self.assertIn("probe", self.s.support("+447700900123")["note"])

    def test_the_probe_plan_is_printed_and_nothing_is_wired(self):
        plan = self.s.probe_plan("+15252627527")
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["wired"], [], "a probe that claims to be wired must actually be wired")
        self.assertEqual(len(plan["probes"]), 3)
        self.assertIn("stranger's phone buzzes", " ".join(p["consequence"] for p in plan["probes"]))
        self.assertIn("undocumented", plan["why_not_run"])
        self.assertEqual(plan["gate"]["env"], "HEYPHONY_LOOKUP")

    def test_an_unknown_service_is_a_refusal_with_the_known_ones(self):
        plan = self.s.probe_plan("+15551234567", service="telegram")
        self.assertFalse(plan["ok"])
        self.assertIn("whatsapp", plan["known"])


class TestTheLookupFlagAnswersBothShapes(unittest.TestCase):
    """the two shapes the owner asked for, from one flag."""

    def _run(self, *argv):
        done = subprocess.run([str(ROOT / "bin" / "heyphony"), *argv],
                              capture_output=True, text=True, timeout=120)
        return done.returncode, json.loads(done.stdout)

    def test_the_bare_lookup_answers_what_the_number_is(self):
        code, answer = self._run("--lookup", "+442071234567")
        self.assertEqual(code, 0)
        self.assertEqual(answer["line"]["type"], "landline")
        self.assertFalse(answer["line"]["receive_text"])

    def test_the_support_mode_answers_per_service(self):
        code, answer = self._run("--lookup", "+15252627527", "support")
        self.assertEqual(code, 0)
        names = [r["service"] for r in answer["services"]]
        self.assertEqual(names, ["sms", "rcs", "imessage", "signal", "whatsapp"])
        self.assertTrue(all(r["verdict"] for r in answer["services"]))

    def test_the_subcommand_is_the_same_answer_as_the_flag(self):
        self.assertEqual(self._run("lookup", "+447700900123", "line")[1],
                         self._run("--lookup", "+447700900123", "line")[1])

    def test_the_probes_mode_prints_the_plan(self):
        code, answer = self._run("--lookup", "+15252627527", "probes")
        self.assertEqual(code, 0)
        self.assertEqual(answer["wired"], [])

    def test_no_number_is_a_usage_answer_not_a_crash(self):
        code, answer = self._run("--lookup")
        self.assertEqual(code, 1)
        self.assertIn("usage", answer)


class TestTheLookupPageMatchesTheCode(unittest.TestCase):
    """the page is the promise, so it is pinned to the data and to the refusals."""

    def setUp(self):
        self.page = (ROOT / "src" / "lookup" / "readme.md").read_text()

    def test_the_page_says_evidence_not_verdicts(self):
        self.assertIn("evidence, not a verdict", self.page)
        self.assertIn("a first-class result", self.page)

    def test_the_page_names_the_probe_consequences(self):
        self.assertIn("sends an sms code to that handset", self.page)
        self.assertIn("undocumented", self.page)

    def test_the_page_states_the_coverage_per_market(self):
        for iso in ("gb", "us and ca", "se, pl, lt, nl, au"):
            self.assertIn(iso, self.page, f"the page does not state coverage for {iso}")

    def test_the_page_has_no_em_dash(self):
        self.assertNotIn("\u2014", self.page)

    def test_the_markets_in_the_code_are_the_markets_on_the_page(self):
        from src.lookup import classify
        for iso in ("GB", "US", "CA", "SE", "PL", "LT", "NL", "AU"):
            self.assertIn(iso, classify.MARKETS)
        self.assertNotIn("FR", classify.MARKETS, "an unseeded market stays unseeded until a table exists")


class TestTheRegionalPlanAnswersGeographyNotLineType(unittest.TestCase):
    """+1 is a plan with 25 members, and the area code is a place rather than a line type."""

    def setUp(self):
        from src.lookup import classify
        self.c = classify

    def test_a_us_area_code_carries_the_state_and_says_nothing_about_the_line(self):
        answer = self.c.classify("+12125551234")
        self.assertEqual(answer["market"], "US")
        self.assertEqual(answer["region"], "New York, NY")
        self.assertEqual(answer["type"], "unknown", "an area code is not a line type")
        self.assertEqual(answer["plan"], "NANP")

    def test_canada_is_the_same_plan_and_a_different_country(self):
        answer = self.c.classify("+14165551234")
        self.assertEqual(answer["market"], "CA")
        self.assertEqual(answer["region"], "Ontario")

    def test_plus_one_is_not_only_the_usa_and_canada(self):
        for number, iso, region in (("+13405551234", "VI", "U.S. Virgin Islands"),
                                    ("+17875551234", "PR", "Puerto Rico"),
                                    ("+12425551234", "BS", "Bahamas"),
                                    ("+18765551234", "JM", "Jamaica"),
                                    ("+18095551234", "DO", "Dominican Republic"),
                                    ("+16715551234", "GU", "Guam"),
                                    ("+14415551234", "BM", "Bermuda")):
            answer = self.c.classify(number)
            self.assertEqual(answer["market"], iso, f"{number} should be {iso}")
            self.assertEqual(answer["region"], region)

    def test_the_table_carries_every_member_the_metadata_names(self):
        from src.lookup import classify
        generated = classify.nanp()["_generated"]
        self.assertEqual(len(classify.nanp()["countries"]), 25)
        self.assertGreater(len(classify.nanp()["area_codes"]), 400)
        self.assertIn("libphonenumber", generated["from"])
        self.assertEqual(generated["by"], "tools/generate_nanp.py")

    def test_a_service_code_is_a_class_the_plan_states(self):
        toll_free = self.c.classify("+18005551234")
        self.assertEqual(toll_free["type"], "toll-free")
        self.assertFalse(toll_free["receive_text"], "nobody signs up with an 800 number")
        premium = self.c.classify("+19005551234")
        self.assertEqual(premium["type"], "premium rate")
        self.assertFalse(premium["receive_text"])
        personal = self.c.classify("+15005551234")
        self.assertEqual(personal["type"], "personal numbering")
        self.assertEqual(personal["receive_text"], "unlikely")

    def test_an_area_code_outside_the_table_stays_unknown(self):
        answer = self.c.classify("+19995551234")
        self.assertEqual(answer["type"], "unknown")
        self.assertEqual(answer["receive_text"], "unknown")
        self.assertIn("199", answer["why"] + "199", "the refusal names the code")

    def test_the_geography_is_answerable_from_the_area_code_alone(self):
        partial = self.c.classify("+1212")
        self.assertTrue(partial["partial"])
        self.assertEqual(partial["market"], "US")
        self.assertEqual(partial["region"], "New York, NY")
        self.assertIn("not needed", partial["privacy"]["enough"])

    def test_every_answer_records_that_nothing_left_the_machine(self):
        answer = self.c.classify("+12125551234")
        self.assertEqual(answer["privacy"]["network"], "no request leaves the machine")
        self.assertEqual(answer["evidence"][0]["strength"], self.c.AREA_CODE)


class TestTheLookupIsEvaluatedBeforeItIsTrusted(unittest.TestCase):
    """the themailtell contract: fixtures, rates, overreach counted separately, no accuracy claim."""

    def setUp(self):
        from src.lookup import evalrun
        self.run = evalrun.run()
        self.evalrun = evalrun

    def test_the_labelled_corpus_passes_and_makes_no_overreach_claims(self):
        self.assertGreaterEqual(self.run["cases"], 18)
        self.assertEqual(self.run["fail"], 0, self.run["failures"])
        self.assertEqual(len(self.run["overreach"]), 0)

    def test_the_unknown_rate_is_reported_rather_than_folded_into_failures(self):
        self.assertGreater(self.run["unknown_rate"], 0)
        self.assertIn("does not prove the table", self.run["how_to_read"])

    def test_the_corpus_has_contrast_pairs_in_the_same_market(self):
        cases = self.evalrun.cases()[0]
        contrasts = [c["contrast"] for c in cases if c.get("contrast")]
        self.assertTrue(contrasts, "a corpus without contrast pairs tests nothing")
        ids = {c["id"] for c in cases}
        for pair in contrasts:
            self.assertIn(pair, ids)

    def test_the_eval_is_reachable_from_the_cli_both_ways(self):
        for argv in (["lookup", "eval"], ["--lookup", "eval"]):
            done = subprocess.run([str(ROOT / "bin" / "heyphony"), *argv],
                                  capture_output=True, text=True, timeout=180)
            self.assertEqual(done.returncode, 0, done.stderr)
            report = json.loads(done.stdout)
            self.assertEqual(report["fail"], 0)
            self.assertEqual(report["overreach"], 0)


class TestTheBuildToolsDoNotLeakIntoTheRuntime(unittest.TestCase):
    """the generator needs a pip install; src/ must keep importing the standard library only."""

    def test_the_tree_carries_no_bytecode_even_untracked(self):
        """no .gitignore means nothing may leave __pycache__ behind, so the tree is checked, not the index."""
        left = sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob("__pycache__")
                      if ".git" not in p.parts)
        self.assertEqual(left, [], f"bytecode on disk: {left}")
        self.assertFalse((ROOT / ".gitignore").exists(), "main carries no ignore file by request")

    def test_the_generator_lives_outside_src_and_says_why(self):
        generator = ROOT / "tools" / "generate_nanp.py"
        self.assertTrue(generator.exists())
        self.assertIn("pip install phonenumbers", generator.read_text())
        self.assertFalse((ROOT / "src" / "lookup" / "generate_nanp.py").exists())

    def test_nothing_in_src_imports_tools_and_no_bytecode_is_tracked(self):
        for path in sorted((ROOT / "src").rglob("*.py")):
            for line in path.read_text().splitlines():
                self.assertNotIn("import tools", line.strip())
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout
        self.assertNotIn(".pyc", tracked, "compiled bytecode is not source")

    def test_the_generated_table_says_where_it_came_from(self):
        import json as _json
        table = _json.loads((ROOT / "src" / "lookup" / "nanp.json").read_text())
        self.assertIn("libphonenumber", table["_generated"]["from"])
        self.assertIn("line type is not in this table", table["_generated"]["what"])


class TestAFieldThePlanCannotFillSaysWhy(unittest.TestCase):
    """an empty field is part of the answer, not a hole: a toll-free number has no region on purpose."""

    def setUp(self):
        from src.lookup import classify
        self.c = classify

    def test_a_toll_free_line_says_its_missing_region_is_the_answer(self):
        answer = self.c.classify("+18005551234")
        self.assertIsNone(answer["region"])
        reason = answer["withheld"]["region"]
        self.assertIn("toll-free", reason)
        self.assertIn("national by design", reason)
        self.assertIn("rather than missing data", reason)

    def test_the_same_number_does_not_claim_a_personal_line_type_either(self):
        answer = self.c.classify("+18005551234")
        self.assertEqual(answer["type"], "toll-free")
        self.assertIn("service line", answer["withheld"]["type"])

    def test_a_premium_and_a_personal_code_are_explained_the_same_way(self):
        for number in ("+19005551234", "+15005551234"):
            answer = self.c.classify(number)
            self.assertIsNone(answer["region"])
            self.assertIn("region", answer["withheld"], number)

    def test_a_geographic_plus_one_withholds_only_the_line_type(self):
        answer = self.c.classify("+12125551234")
        self.assertEqual(answer["region"], "New York, NY")
        self.assertEqual(list(answer["withheld"]), ["type"])
        self.assertIn("does not encode line type", answer["withheld"]["type"])

    def test_a_mobile_in_a_per_range_market_withholds_a_region_it_never_had(self):
        answer = self.c.classify("+447700900123")
        self.assertIsNone(answer["region"])
        self.assertIn("not tied to a place", answer["withheld"]["region"])

    def test_a_market_with_no_table_withholds_every_answer_it_cannot_give(self):
        answer = self.c.classify("+33612345678")
        self.assertEqual(sorted(answer["withheld"]), ["receive_text", "region", "type"])
        self.assertIn("unanswered rather than guessed", answer["withheld"]["type"])

    def test_an_unknown_area_code_says_the_table_is_what_is_missing(self):
        answer = self.c.classify("+19995551234")
        self.assertIn("does not carry this area code", answer["withheld"]["region"])

    def test_a_partial_area_code_lookup_keeps_the_same_reasons(self):
        partial = self.c.classify("+1800")
        self.assertIn("toll-free", partial["withheld"]["region"])

    def test_the_page_says_an_empty_region_is_the_plan_being_exact(self):
        page = (ROOT / "src" / "lookup" / "readme.md").read_text()
        self.assertIn("a field the plan cannot fill is part of the answer", page)
        self.assertIn("toll-free", page)


class TestAnAddressSaysWhatItCanAboutImessage(unittest.TestCase):
    """the address half: two classes, one verdict, and no probability pretending to be one."""

    def setUp(self):
        from src.lookup import email
        self.e = email

    def test_an_apple_address_is_an_apple_account_by_construction(self):
        for address in ("dana@icloud.com", "dana@me.com", "dana@mac.com"):
            found = self.e.lookup(address)
            self.assertEqual(found["domain_class"], "apple account address", address)
            self.assertEqual(found["imessage"], "possible")
        self.assertNotIn("reachable_by_imessage", self.e.lookup("dana@icloud.com")["withheld"])

    def test_a_consumer_mailbox_is_unknown_because_it_could_be_either(self):
        found = self.e.lookup("dana@gmail.com")
        self.assertEqual(found["domain_class"], "consumer mailbox")
        self.assertEqual(found["imessage"], "unknown")
        self.assertIn("most of them are not used as one", found["why"])

    def test_a_desk_is_not_a_person_and_says_so(self):
        found = self.e.lookup("support@acme.co.uk")
        self.assertEqual(found["local_class"], "role address")
        self.assertEqual(found["imessage"], "unlikely")
        self.assertIn("whoever is on shift", found["why"])

    def test_two_addresses_at_one_domain_get_different_verdicts(self):
        desk = self.e.lookup("support@acme.co.uk")
        person = self.e.lookup("dana@acme.co.uk")
        self.assertEqual(desk["domain_class"], person["domain_class"])
        self.assertEqual((desk["imessage"], person["imessage"]), ("unlikely", "unknown"))

    def test_a_throwaway_domain_is_unlikely_rather_than_unknown(self):
        found = self.e.lookup("dana@mailinator.com")
        self.assertEqual(found["domain_class"], "disposable domain")
        self.assertEqual(found["imessage"], "unlikely")

    def test_a_tag_is_part_of_the_address_and_not_the_identity(self):
        found = self.e.lookup("dana+lists@proton.me")
        self.assertEqual(found["local_class"], "personal mailbox with a tag")

    def test_a_malformed_address_is_refused_with_the_reason(self):
        for address, needle in (("dana@localhost", "at least one dot"), ("dana@@x.com", "one @"),
                                ("dana@-x.com", "not a domain"), ("dana smith@x.com", "cannot")):
            found = self.e.lookup(address)
            self.assertFalse(found["valid"], address)
            self.assertIn(needle, found["why"], address)
            self.assertEqual(found["imessage"], "unknown")

    def test_existence_and_deliverability_are_withheld_rather_than_guessed(self):
        found = self.e.lookup("dana@gmail.com")
        self.assertEqual(sorted(found["withheld"]), ["deliverable", "exists", "reachable_by_imessage"])
        names = [row["name"] for row in found["probes"]]
        self.assertEqual(names, ["dns-mx", "smtp-rcpt"])
        self.assertFalse(any(row["wired"] for row in found["probes"]))


class TestAHandleIsWhereANumberIsNotNeeded(unittest.TestCase):
    """the username half, and the ambiguity that makes it worth having."""

    def setUp(self):
        from src.lookup import handles
        self.h = handles

    def test_signal_wants_a_nickname_and_a_discriminator(self):
        found = self.h.lookup("alice.42")
        self.assertEqual(found["platform"], "signal")
        self.assertTrue(found["valid"])
        self.assertTrue(found["contactable_without_number"])
        self.assertFalse(found["number_known"])

    def test_a_bare_nickname_reaches_nobody_on_signal(self):
        found = self.h.lookup("alice", "signal")
        self.assertFalse(found["valid"])
        self.assertIn("signal adds the number itself", found["why"])

    def test_a_bare_handle_is_whatsapps_shape(self):
        for value in ("alice", "@alice"):
            found = self.h.lookup(value)
            self.assertEqual(found["platform"], "whatsapp", value)
            self.assertTrue(found["valid"], value)
        self.assertTrue(self.h.lookup("@alice")["typed_at"])

    def test_the_same_string_is_legal_on_both_and_names_two_accounts(self):
        found = self.h.lookup("alice.42")
        self.assertEqual([row["platform"] for row in found["also_read_as"]], ["whatsapp"])
        self.assertIn("different account", found["also_read_as"][0]["note"])

    def test_a_short_discriminator_is_signal_shaped_and_too_short(self):
        found = self.h.lookup("alice.4")
        self.assertEqual(found["platform"], "signal")
        self.assertFalse(found["valid"])
        self.assertEqual([row["platform"] for row in found["also_read_as"]], ["whatsapp"])

    def test_a_handle_is_a_handle_and_not_an_identity(self):
        found = self.h.lookup("alice.42")
        self.assertIn("hash", found["withheld"]["stability"])
        self.assertIn("changed", found["withheld"]["stability"])
        self.assertIn("handle rather than an identity", found["withheld"]["identity"])

    def test_whatsapps_key_is_named_because_a_username_is_not_always_enough(self):
        found = self.h.lookup("alice")
        self.assertIn("four digit username key", found["withheld"]["chat"])

    def test_the_only_probe_that_sends_is_a_first_message_and_it_is_refused(self):
        signal_probe = self.h.lookup("alice.42")["probes"][0]
        whatsapp_probe = self.h.lookup("alice")["probes"][0]
        self.assertTrue(signal_probe["sends_nothing"])
        self.assertFalse(whatsapp_probe["sends_nothing"])
        self.assertIn("is contact", whatsapp_probe["refused"])

    def test_the_carried_rules_admit_they_are_unverified(self):
        table = self.h.platforms()["platforms"]
        for name, entry in table.items():
            self.assertFalse(entry["verified"], name)
            self.assertTrue(entry["sources"], name)
            self.assertTrue(entry["notes"], name)
        self.assertIn("only the rules marked fatal decide validity",
                      self.h.platforms()["_limit"])

    def test_an_outside_bound_is_reported_without_calling_the_handle_invalid(self):
        found = self.h.lookup("x" * 40, "whatsapp")
        self.assertTrue(found["valid"], "a wrong bound must not invalidate a real handle")
        self.assertIn("outside_shape", found)
        self.assertIn("at most 35", found["outside_shape"][0])


class TestTheOsintToolsAreNamedRatherThanReimplemented(unittest.TestCase):
    """the probing half exists as turnkey tools, and the page says so instead of hiding it."""

    def setUp(self):
        page = (ROOT / "src" / "lookup" / "readme.md").read_text()
        # read it as one line, so a sentence that wraps in the source still reads as a sentence
        self.page = " ".join(page.split())

    def test_the_page_names_the_turnkey_tools_and_their_inputs(self):
        for needle in ("`holehe`", "`sherlock`", "`maigret`", "`phoneinfoga`",
                       "forgot password", "dns mx"):
            self.assertIn(needle, self.page)

    def test_the_page_gives_the_three_reasons_the_probing_half_is_outside(self):
        for needle in ("The cost lands on the person being looked up", "The coverage rots",
                       "The scale is wrong"):
            self.assertIn(needle, self.page)

    def test_no_osint_tool_is_imported_or_shelled_out_to(self):
        source = "".join(p.read_text() for p in sorted((ROOT / "src").rglob("*.py")))
        for name in ("holehe", "sherlock", "maigret", "phoneinfoga"):
            self.assertNotIn(f"import {name}", source)
            self.assertNotIn(name, source.split("readme")[0])
        self.assertNotIn("subprocess", (ROOT / "src" / "lookup" / "classify.py").read_text())

    def test_the_reader_still_sends_nothing_for_any_kind(self):
        from src.lookup import classify
        for value in ("+12125551234", "dana@icloud.com", "alice.42"):
            answer = classify.classify(value)
            self.assertEqual(answer["privacy"]["network"], "no request leaves the machine", value)
            self.assertFalse(answer["verified"], value)


class TestResolvingAHandleIsNotScanningForOne(unittest.TestCase):
    """the good instrument for one person: one exact string, your own identity, nothing sent."""

    def setUp(self):
        from src.lookup import handles
        self.h = handles
        self.page = " ".join((ROOT / "src" / "lookup" / "readme.md").read_text().split())

    def test_signal_offers_a_resolve_and_says_it_sends_nothing(self):
        probe = self.h.lookup("alice.42")["probes"][0]
        self.assertEqual(probe["name"], "resolve")
        self.assertTrue(probe["sends_nothing"])
        self.assertFalse(probe["wired"])

    def test_the_resolve_names_the_identity_it_needs_and_the_library_it_rides(self):
        probe = self.h.lookup("alice.42")["probes"][0]
        self.assertIn("heyphony get signal", probe["needs"])
        self.assertIn("libsignal", probe["needs"])
        self.assertIn("signal-whois", probe["needs"])

    def test_one_string_is_a_resolution_and_a_loop_is_an_oracle(self):
        probe = self.h.lookup("alice.42")["probes"][0]
        self.assertIn("username oracle", probe["one_at_a_time"])
        self.assertIn("rate limits", probe["one_at_a_time"])

    def test_an_account_id_is_a_pseudonym_and_the_stable_thing(self):
        probe = self.h.lookup("alice.42")["probes"][0]
        self.assertIn("pseudonym", probe["what_it_does_not_say"])
        self.assertIn("username is not", probe["what_it_does_not_say"])

    def test_whatsapp_has_no_resolver_so_the_only_check_is_a_message(self):
        probe = self.h.lookup("alice")["probes"][0]
        self.assertEqual(probe["name"], "open-a-chat")
        self.assertFalse(probe["sends_nothing"])
        self.assertFalse(probe["wired"])
        self.assertIn("no resolution endpoint", probe["refused"])

    def test_no_resolve_runs_and_nothing_leaves_the_machine(self):
        for value in ("alice.42", "alice"):
            answer = self.h.lookup(value)
            self.assertFalse(any(row["wired"] for row in answer["probes"]), value)
            self.assertEqual(answer["privacy"]["network"], "no request leaves the machine", value)

    def test_the_page_puts_resolve_ahead_of_scanning_and_says_why_asking_wins(self):
        for needle in ("Resolve, do not scan", "kpcyrd/signal-whois", "own registered identity",
                       "username oracle", "the stable thing to keep while the username is not",
                       "And ask."):
            self.assertIn(needle, self.page)

    def test_the_page_keeps_reuse_in_view_because_hands_change(self):
        self.assertIn("somebody else can claim it", self.page)


class TestACapabilityIsABooleanAndExistenceIsNot(unittest.TestCase):
    """the two questions an address asks, answered separately so neither has to be invented."""

    def setUp(self):
        from src.lookup import support
        self.s = support

    def test_an_address_holds_imessage_however_the_mailbox_turns_out(self):
        for address in ("examplemail@gmail.com", "someone@icloud.com", "support@acme.co.uk",
                        "dana@mailinator.com"):
            matrix = self.s.support(address)["matrix"]
            self.assertTrue(matrix["imessage"], address)

    def test_an_address_holds_none_of_the_services_that_verify_by_number(self):
        matrix = self.s.support("examplemail@gmail.com")["matrix"]
        self.assertEqual((matrix["signal"], matrix["whatsapp"], matrix["sms"]), (False, False, False))

    def test_the_same_address_keeps_its_own_unknown_verdict(self):
        answer = self.s.support("examplemail@gmail.com")
        self.assertTrue(answer["matrix"]["imessage"])
        self.assertEqual(answer["address"]["imessage"], "unknown")
        self.assertIn("exists", answer["address"]["withheld"])

    def test_an_apple_address_is_capable_and_possible_while_gmail_is_capable_and_unknown(self):
        apple = self.s.support("someone@icloud.com")
        gmail = self.s.support("examplemail@gmail.com")
        self.assertEqual(apple["matrix"], gmail["matrix"])
        self.assertEqual((apple["address"]["imessage"], gmail["address"]["imessage"]),
                         ("possible", "unknown"))

    def test_a_handle_holds_its_own_platform_and_cannot_hold_the_other(self):
        signal = self.s.support("alice.42")["matrix"]
        whatsapp = self.s.support("alice")["matrix"]
        self.assertEqual((signal["signal"], signal["whatsapp"]), (True, False))
        self.assertEqual((whatsapp["whatsapp"], whatsapp["signal"]), (True, False))

    def test_a_line_leaves_the_account_question_open_rather_than_guessing(self):
        matrix = self.s.support("+12125551234")["matrix"]
        self.assertEqual((matrix["imessage"], matrix["signal"], matrix["whatsapp"]), (None, None, None))
        self.assertTrue(matrix["sms"])

    def test_a_service_range_can_hold_none_of_them(self):
        matrix = self.s.support("+18005551234")["matrix"]
        self.assertEqual(set(matrix.values()), {False})

    def test_the_matrix_says_which_question_its_booleans_answer(self):
        answer = self.s.support("examplemail@gmail.com")
        self.assertIn("can hold this service at all", answer["matrix_means"])
        self.assertIn("not a claim that this particular one is registered", answer["matrix_means"])

    def test_an_invalid_input_holds_nothing_rather_than_unknown_everything(self):
        self.assertEqual(set(self.s.support("dana@localhost")["matrix"].values()), {False})

    def test_the_page_puts_capability_and_existence_side_by_side(self):
        page = " ".join((ROOT / "src" / "lookup" / "readme.md").read_text().split())
        for needle in ("a boolean for the capability and a verdict for this one",
                       "imessage: true signal: false",
                       "Both lines are in the same output"):
            self.assertIn(needle, page)


class TestTheLadderWhenOneRailIsNotThere(unittest.TestCase):
    """an address holds imessage whatever it is, and a line climbs to rcs when apple is not there."""

    def setUp(self):
        from src.lookup import support
        self.s = support

    def test_any_address_holds_imessage_and_not_only_an_apple_one(self):
        for address in ("dana@proton.me", "dana@outlook.com", "dana@yahoo.co.uk",
                        "dana@somewhere-unheard-of.example", "dana@mailinator.com",
                        "support@acme.co.uk"):
            matrix = self.s.support(address)["matrix"]
            self.assertTrue(matrix["imessage"], address)

    def test_every_address_gets_the_same_capability_and_a_different_verdict(self):
        consumer = self.s.support("dana@outlook.com")
        apple = self.s.support("dana@icloud.com")
        self.assertEqual(consumer["matrix"], apple["matrix"])
        self.assertEqual(consumer["address"]["imessage"], "unknown")
        self.assertEqual(apple["address"]["imessage"], "possible")

    def test_rcs_is_in_the_matrix_and_follows_the_text_evidence(self):
        mobile = self.s.support("+12125551234")["matrix"]
        toll_free = self.s.support("+18005551234")["matrix"]
        landline = self.s.support("+441234567890")["matrix"]
        self.assertTrue(mobile["rcs"])
        self.assertFalse(toll_free["rcs"])
        self.assertFalse(landline["rcs"])
        for matrix in (mobile, toll_free, landline):
            self.assertEqual(matrix["rcs"], matrix["sms"], matrix)

    def test_an_address_and_a_handle_cannot_hold_rcs_because_it_verifies_by_number(self):
        self.assertFalse(self.s.support("dana@proton.me")["matrix"]["rcs"])
        self.assertFalse(self.s.support("alice.42")["matrix"]["rcs"])

    def test_a_line_climbs_apple_then_carrier_then_text(self):
        ladder = self.s.support("+12125551234")["fallback"]
        self.assertEqual(ladder["order"], ["imessage", "rcs", "sms"])
        self.assertEqual(ladder["reaches"], "rcs")
        self.assertEqual(ladder["unknown"], ["imessage"])
        self.assertIsNone(ladder["stops_because"])

    def test_a_ladder_that_reaches_nothing_says_no_client_will_fix_it(self):
        ladder = self.s.support("+18005551234")["fallback"]
        self.assertIsNone(ladder["reaches"])
        self.assertIn("will not change the answer", ladder["stops_because"])

    def test_an_address_climbs_one_rung_and_a_handle_climbs_its_own(self):
        self.assertEqual(self.s.support("dana@proton.me")["fallback"]["order"], ["imessage"])
        self.assertEqual(self.s.support("dana@proton.me")["fallback"]["reaches"], "imessage")
        self.assertEqual(self.s.support("alice.42")["fallback"]["order"], ["signal"])
        self.assertEqual(self.s.support("alice.42")["fallback"]["reaches"], "signal")
        self.assertEqual(self.s.support("alice")["fallback"]["reaches"], "whatsapp")

    def test_the_ladder_never_promises_a_rail_its_matrix_denies(self):
        for value in ("+12125551234", "+18005551234", "dana@proton.me", "alice.42", "alice"):
            answer = self.s.support(value)
            matrix, ladder = answer["matrix"], answer["fallback"]
            for rail in ladder["rails"]:
                self.assertEqual(rail["holds"], matrix[rail["service"]], (value, rail["service"]))
            self.assertEqual(ladder["reaches"],
                             next((r["service"] for r in ladder["rails"] if r["holds"] is True), None))

    def test_the_ladder_keeps_the_person_out_of_the_boolean(self):
        ladder = self.s.support("+12125551234")["fallback"]
        self.assertIn("does not replace asking them", ladder["means"])
        self.assertIn("does not say which one somebody's messaging app will pick", ladder["means"])

    def test_the_cli_fallback_mode_answers_the_question_on_its_own(self):
        sys.path.insert(0, str(ROOT))
        from src.runner import cli
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cli.cmd_lookup({"number": "+12125551234", "mode": "fallback", "platform": None})
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buffer.getvalue())["fallback"]["reaches"], "rcs")

    def test_the_page_names_the_ladder_and_rcs_as_its_own_rung(self):
        page = " ".join((ROOT / "src" / "lookup" / "readme.md").read_text().split())
        for needle in ("## the ladder when one rail is not there", "### rcs is the rung the matrix was missing",
                       "### an address holds iMessage whatever the address is",
                       "reaches: rcs", "no universal profile to answer on"):
            self.assertIn(needle, page)


class TestAGroupReplyComesBackAsAStranger(unittest.TestCase):
    """the carrier carries no group thread, so inbound attribution is ours and has to say so."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        os.environ["HEYPHONY_GROUPS"] = os.path.join(self.tmp, "groups.json")
        self.did = "+15550000000"
        from src.manage import groups
        self.g = groups
        self.g.create("friday crew", [{"name": "ada", "number": "+15550000001"},
                                      {"name": "bo", "number": "+15550000002"}])
        self.g.create("sunday", [{"name": "ada", "number": "+15550000001"},
                                 {"name": "cy", "number": "+15550000003"}])
        os.environ["VOIPMS_API_USER"] = "user"
        os.environ["VOIPMS_API_PASS"] = "secret"
        os.environ["HEYPHONY_SEND"] = "allowed"
        self.inbox = [{"id": "m1", "sender": "+15550000002", "recipient": self.did,
                       "body": "who is driving", "at": 100},
                      {"id": "m2", "sender": "+15550000003", "recipient": self.did,
                       "body": "still on for sunday", "at": 200},
                      {"id": "m3", "sender": "+15559999999", "recipient": self.did,
                       "body": "wrong number", "at": 300}]

    def tearDown(self):
        for name in ("HEYPHONY_GROUPS", "HEYPHONY_SEND", "XDG_DATA_HOME"):
            os.environ.pop(name, None)

    def test_membership_is_read_from_our_records_not_the_carrier(self):
        hits = self.g.attribute(self.g.load()["groups"], "+15550000002")
        self.assertEqual([h["name"] for h in hits], ["friday crew"])
        self.assertEqual(hits[0]["member"], "bo")

    def test_a_number_in_two_groups_gets_both_rather_than_a_picked_one(self):
        hits = self.g.attribute(self.g.load()["groups"], "+15550000001")
        self.assertEqual([h["name"] for h in hits], ["friday crew", "sunday"])

    def test_a_stranger_belongs_to_nothing(self):
        self.assertEqual(self.g.attribute(self.g.load()["groups"], "+15559999999"), [])

    def test_the_thread_holds_sends_and_replies_in_one_order(self):
        self.g.say("friday crew", "seven o'clock", provider="voip.ms", from_number=self.did,
                   opener=lambda request: (200, "{}"))
        thread = self.g.thread("friday crew", messages=self.inbox)
        self.assertTrue(thread["ok"])
        self.assertEqual([row["direction"] for row in thread["rows"]], ["in", "out"])
        self.assertEqual(thread["rows"][0]["who"], "bo")
        self.assertIn("matched by membership", thread["means"])

    def test_an_inbound_row_is_named_rather_than_dressed_up_as_a_group_message(self):
        thread = self.g.thread("friday crew", messages=self.inbox)
        self.assertIn("a member's own text", thread["means"])
        self.assertFalse(any("group_id" in row for row in thread["rows"]))

    def test_a_reply_goes_to_every_member_through_the_same_rail(self):
        seen = []

        def opener(request):
            seen.append(request)
            return 200, "{}"

        answer = self.g.reply("friday crew", "seven then", provider="voip.ms",
                              from_number=self.did, allow=True, opener=opener,
                              replying="+15550000002")
        self.assertTrue(answer["reply"])
        self.assertEqual((answer["sent"], answer["of"]), (2, 2))
        self.assertEqual(len(seen), 2)
        self.assertIn("same one-to-one thread they used", answer["means"])

    def test_a_draft_carries_the_same_explanation_as_a_sent_reply(self):
        answer = self.g.reply("friday crew", "seven then", provider="voip.ms",
                              from_number=self.did, allow=False,
                              opener=lambda request: (200, "{}"))
        self.assertTrue(answer["draft"])
        self.assertTrue(answer["reply"])
        self.assertIn("no group thread exists", answer["means"])

    def test_the_reply_still_refuses_the_things_the_rail_refuses(self):
        answer = self.g.reply("friday crew", "seven then", provider="voip.ms",
                              from_number=self.did, allow=False,
                              opener=lambda request: (200, "{}"))
        self.assertIn("each member gets a one-to-one text", answer["what_members_see"])
        self.assertEqual((answer["sent"], answer["of"]), (0, 2))
        self.assertIn("cannot text the group", answer["what_members_see"])

    def test_the_inbox_row_names_the_group_without_storing_it(self):
        from src.manage import views
        os.environ["XDG_DATA_HOME"] = self.tmp
        os.makedirs(os.path.join(self.tmp, "telephony"), exist_ok=True)
        with open(os.path.join(self.tmp, "telephony", "inbox.jsonl"), "w") as handle:
            for entry in self.inbox:
                handle.write(json.dumps({"id": entry["id"], "channel": "sms",
                                         "direction": "in", "sender": entry["sender"],
                                         "recipient": self.did, "body": entry["body"],
                                         "at": entry["at"]}) + "\n")
        view = views.messages(home=self.tmp, limit=10)
        by_from = {row["from"]: row for row in view["rows"]}
        self.assertEqual(by_from["+15550000002"]["groups"][0]["name"], "friday crew")
        self.assertIn("their own text", by_from["+15550000002"]["note"])
        self.assertNotIn("groups", by_from["+15559999999"])
        stored = open(os.path.join(self.tmp, "telephony", "inbox.jsonl")).read()
        self.assertNotIn("friday crew", stored)

    def test_the_page_states_the_two_limits_of_attribution(self):
        page = " ".join((ROOT / "readme.md").read_text().split())
        for needle in ("### what comes back, and how a reply is answered",
                       "resolves that name **at read time**",
                       "a real carrier group mms", "indistinguishable from their group reply"):
            self.assertIn(needle, page)


class TestTheCodeAGroupCarries(unittest.TestCase):
    """membership is a guess, so a group gets a code a reply can quote instead."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        os.environ["HEYPHONY_GROUPS"] = os.path.join(self.tmp, "groups.json")
        os.environ["VOIPMS_API_USER"] = "user"
        os.environ["VOIPMS_API_PASS"] = "secret"
        os.environ["HEYPHONY_SEND"] = "allowed"
        from src.manage import groups
        self.g = groups
        self.did = "+15550000000"
        self.made = self.g.create("friday crew", [{"name": "ada", "number": "+15550000001"},
                                                  {"name": "bo", "number": "+15550000002"}])
        self.code = self.made["code"]
        self.g.create("sunday", [{"name": "ada", "number": "+15550000001"},
                                 {"name": "cy", "number": "+15550000003"}])

    def tearDown(self):
        for name in ("HEYPHONY_GROUPS", "HEYPHONY_SEND", "VOIPMS_API_USER", "VOIPMS_API_PASS"):
            os.environ.pop(name, None)

    def test_the_code_is_four_characters_nobody_can_confuse(self):
        self.assertEqual(len(self.code), 4)
        for character in self.code:
            self.assertIn(character, self.g.CODE_ALPHABET)
        for confusable in "BIOS01258":
            self.assertNotIn(confusable, self.g.CODE_ALPHABET)

    def test_two_live_groups_never_answer_to_the_same_code(self):
        codes = [group["code"] for group in self.g.load()["groups"]]
        self.assertEqual(len(codes), len(set(codes)))

    def test_the_tag_rides_on_what_leaves_and_the_body_stays_the_body(self):
        sent = {}

        def opener(request):
            sent.setdefault("requests", []).append(request)
            return 200, "{}"

        answer = self.g.say("friday crew", "seven then", provider="voip.ms",
                            from_number=self.did, allow=True, opener=opener)
        self.assertEqual(answer["tag"], f"ref {self.code}")
        self.assertEqual(len(sent["requests"]), 2)
        self.assertIn(self.code, json.dumps(sent["requests"][0]))
        stored = self.g.load()["groups"][0]["messages"][0]
        self.assertEqual(stored["text"], "seven then")
        self.assertIn(f"ref {self.code}", stored["sent_text"])

    def test_no_tag_sends_the_body_alone_and_says_so_by_omission(self):
        answer = self.g.say("friday crew", "seven then", provider="voip.ms", from_number=self.did,
                            allow=False, tag=False, opener=lambda request: (200, "{}"))
        self.assertIsNone(answer["tag"])

    def test_the_output_names_the_segment_cost_of_the_tag(self):
        answer = self.g.say("friday crew", "seven then", provider="voip.ms", from_number=self.did,
                            allow=False, opener=lambda request: (200, "{}"))
        self.assertIn("second segment", answer["segments"])
        self.assertIn("--no-tag", answer["segments"])

    def test_a_quoted_code_is_certain_even_from_a_number_we_never_recorded(self):
        found = self.g.attribute_inbound(sender="+15557777777", text=f"on my way\n\nref {self.code}")
        self.assertEqual(found["by"], "code")
        self.assertTrue(found["certain"])
        self.assertEqual([g["name"] for g in found["groups"]], ["friday crew"])
        self.assertIsNone(found["groups"][0]["member"])

    def test_a_code_settles_a_member_who_is_in_two_groups(self):
        guessed = self.g.attribute_inbound(sender="+15550000001", text="sounds good")
        self.assertEqual(guessed["by"], "ambiguous")
        self.assertFalse(guessed["certain"])
        self.assertEqual(len(guessed["groups"]), 2)
        settled = self.g.attribute_inbound(sender="+15550000001",
                                          text=f"sounds good\n\nref {self.code}")
        self.assertEqual(settled["by"], "code")
        self.assertEqual([g["name"] for g in settled["groups"]], ["friday crew"])
        self.assertEqual(settled["groups"][0]["member"], "ada")

    def test_a_member_can_answer_with_the_code_alone(self):
        self.assertEqual(self.g.code_of(self.code), self.code)
        self.assertEqual(self.g.code_of(f"  {self.code.lower()} "), self.code)
        self.assertIsNone(self.g.code_of("sounds good"))
        self.assertIsNone(self.g.code_of("ok"))
        found = self.g.attribute_inbound(sender="+15550000002", text=self.code)
        self.assertEqual(found["by"], "code")
        self.assertEqual(found["groups"][0]["member"], "bo")

    def test_a_body_that_merely_looks_like_a_code_is_not_one(self):
        self.assertIsNone(self.g.code_of("ACDE is the start of the alphabet"))
        self.assertIsNone(self.g.code_of("see you at 4"))

    def test_a_group_with_a_number_of_its_own_is_addressed_rather_than_guessed(self):
        self.g.create("dinner", [{"name": "ada", "number": "+15550000001"},
                                 {"name": "dee", "number": "+15550000004"}],
                      number="+15550009999")
        found = self.g.attribute_inbound(sender="+15550000004", text="table for four",
                                         recipient="+15550009999")
        self.assertEqual(found["by"], "number")
        self.assertTrue(found["certain"])
        self.assertEqual([g["name"] for g in found["groups"]], ["dinner"])

    def test_the_code_is_never_dressed_up_as_a_secret(self):
        answer = self.made
        self.assertIn("not a person", answer["the_code_is_not_a_secret"])
        self.assertIn("never a way to prove who is writing", answer["the_code_is_not_a_secret"])
        self.assertIn("not a secret", answer["the_code_is_not_a_secret"])

    def test_the_page_names_the_ladder_and_what_the_code_cannot_do(self):
        page = " ".join((ROOT / "readme.md").read_text().split())
        for needle in ("### the code the group carries, so a reply can name itself",
                       "eight characters and no more", 'by: "code"', 'by: "ambiguous"',
                       "and the code is not a secret"):
            self.assertIn(needle, page)


class TestAGroupIsTheThreadTheCarrierCarries(unittest.TestCase):
    """a group chat is an id a carrier carries, so the thread outranks membership and a code."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        os.environ["HEYPHONY_GROUPS"] = os.path.join(self.tmp, "groups.json")
        os.environ["VOIPMS_API_USER"] = "user"
        os.environ["VOIPMS_API_PASS"] = "secret"
        from src.manage import groups
        from src.manage.outgoing import send as outbox
        self.g, self.outbox = groups, outbox
        self.made = self.g.adopt_thread("gc-77", ["ada=+15550000001", "+15550000002"],
                                        name="friday crew")
        self.g.create("sunday", [{"name": "ada", "number": "+15550000001"},
                                 {"name": "cy", "number": "+15550000003"}])

    def tearDown(self):
        for name in ("HEYPHONY_GROUPS", "VOIPMS_API_USER", "VOIPMS_API_PASS"):
            os.environ.pop(name, None)

    def test_an_adopted_thread_is_the_group_and_says_where_it_came_from(self):
        self.assertTrue(self.made["adopted"])
        self.assertEqual(self.made["group"]["thread"], "gc-77")
        self.assertEqual(self.made["group"]["adopted_from"], "carrier")
        self.assertIn("group reply for everybody", self.made["means"])

    def test_adopting_the_same_thread_twice_does_not_duplicate_it(self):
        again = self.g.adopt_thread("gc-77", ["+15550000009"])
        self.assertFalse(again["adopted"])
        self.assertEqual(len([g for g in self.g.load()["groups"] if g.get("thread") == "gc-77"]), 1)

    def test_a_thread_naming_one_person_is_not_a_group_and_says_why(self):
        refused = self.g.adopt_thread("gc-88", ["+15550000001"])
        self.assertFalse(refused["ok"])
        self.assertIn("not a group", refused["why"])
        self.assertIn("nothing to reply to", refused["from_carrier"])

    def test_the_thread_outranks_a_code_and_membership(self):
        found = self.g.attribute_inbound(sender="+15550000001", text="sounds good", thread="gc-77")
        self.assertEqual(found["by"], "thread")
        self.assertTrue(found["certain"])
        self.assertEqual([g["name"] for g in found["groups"]], ["friday crew"])
        self.assertEqual(found["groups"][0]["member"], "ada")

    def test_a_carrier_names_numbers_so_a_thread_member_keeps_the_name_a_human_gave_it(self):
        members = self.g.adopt_thread("gc-77")["group"]["members"]
        self.assertEqual([m["name"] for m in members], ["ada", "+15550000002"])

    def test_a_thread_id_is_never_invented_for_a_plain_text(self):
        self.assertEqual(self.g.attribute_inbound(sender="+15550000001", text="hi")["by"], "ambiguous")
        self.assertEqual(self.g.attribute_inbound(sender="+15557777777", thread="gc-99")["by"], None)

    def test_the_envelope_reads_a_thread_and_its_participants_when_a_carrier_sends_them(self):
        sys.path.insert(0, str(ROOT))
        from src.setup import routes
        payload = {"from": "+15550000001", "to": "+15550000000", "body": "hi",
                   "thread_id": "gc-77", "participants": "+15550000001,+15550000002"}
        envelope = routes.normalize("voip.ms", payload)
        self.assertEqual(envelope["thread"], "gc-77")
        self.assertEqual(envelope["participants"], ["+15550000001", "+15550000002"])
        self.assertIsNone(routes.normalize("voip.ms", {"from": "+1", "body": "hi"})["thread"])

    def test_no_wired_path_claims_it_can_address_a_thread(self):
        for provider, row in self.outbox.THREAD_SEND.items():
            self.assertNotEqual(row["state"], "thread", provider)
            self.assertTrue(row["why"], provider)
        self.assertEqual(set(self.outbox.THREAD_SEND), set(self.outbox.PATHS))
        signalwire = self.outbox.thread_send("signalwire")
        self.assertFalse(signalwire["ok"])
        self.assertIn("single e164 string", signalwire["why"])

    def test_a_reply_to_a_thread_group_states_the_gap_rather_than_implying_a_group_reply(self):
        answer = self.g.say("friday crew", "seven then", provider="voip.ms",
                            from_number="+15550000000", allow=False,
                            opener=lambda request: (200, "{}"))
        self.assertEqual(answer["delivered_as"], "fanout")
        self.assertEqual(answer["thread"], "gc-77")
        self.assertIn("will not appear in the group chat", answer["thread_gap"])
        self.assertIn("one dst per call", answer["thread_gap"])

    def test_a_fan_out_group_has_no_gap_because_it_never_promised_a_thread(self):
        answer = self.g.say("sunday", "still on", provider="voip.ms", from_number="+15550000000",
                            allow=False, opener=lambda request: (200, "{}"))
        self.assertIsNone(answer["thread"])
        self.assertIsNone(answer["thread_gap"])

    def test_the_inbox_row_keeps_the_carrier_thread_apart_from_the_display_thread(self):
        from src.manage import views
        os.environ["XDG_DATA_HOME"] = self.tmp
        os.makedirs(os.path.join(self.tmp, "telephony"), exist_ok=True)
        with open(os.path.join(self.tmp, "telephony", "inbox.jsonl"), "w") as handle:
            handle.write(json.dumps({"id": "t1", "channel": "sms", "direction": "in",
                                     "sender": "+15550000002", "recipient": "+15550000000",
                                     "body": "who is driving", "at": 100, "thread": "gc-77"}) + "\n")
        try:
            row = views.messages(home=self.tmp, limit=5)["rows"][0]
            self.assertEqual(row["carrier_thread"], "gc-77")
            self.assertEqual(row["attributed_by"], "thread")
            self.assertTrue(row["certain"])
        finally:
            os.environ.pop("XDG_DATA_HOME", None)

    def test_the_page_states_the_correction_instead_of_the_old_blanket_claim(self):
        page = " ".join((ROOT / "readme.md").read_text().split())
        module = " ".join((ROOT / "src" / "manage" / "groups.py").read_text().split())
        self.assertIn("### the thread, and the correction that the group is the id", page)
        self.assertIn('by: "thread"', page)
        self.assertIn("was wrong about the carriers", page)
        self.assertNotIn("most carriers do not carry a group sms as a group", page)
        self.assertNotIn("most carriers do not carry a group sms as a group", module)
        self.assertIn("group adopt --thread", page)



class TestWhoTheAgentWillHearFrom(unittest.TestCase):
    """the door is closed by default, the modes are one choice, and a refusal is counted but never stored."""

    def setUp(self):
        from src.manage import allow
        self.allow = allow
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def policy(self, **kw):
        base = self.allow.default_policy()
        base.update(kw)
        return base

    def test_an_unset_policy_admits_nobody(self):
        ok, why = self.allow.decide("+447700900123", self.allow.default_policy())
        self.assertFalse(ok)
        self.assertEqual(why, "not-on-the-list")
        self.assertEqual(self.allow.DEFAULT_MODE, "list", "protection must not depend on being switched on")

    def test_a_missing_or_broken_file_closes_the_door(self):
        missing = self.allow.load(self.tmp / "nope.json")
        self.assertEqual(missing["mode"], "list")
        broken = self.tmp / "broken.json"
        broken.write_text("{ this is not json")
        loaded = self.allow.load(broken)
        self.assertEqual(loaded["mode"], "list")
        self.assertTrue(loaded.get("broken"))
        self.assertFalse(self.allow.decide("+447700900123", loaded)[0])

    def test_an_unknown_mode_in_the_file_falls_back_to_closed(self):
        bad = self.tmp / "bad.json"
        bad.write_text(json.dumps({"mode": "everyone-please"}))
        self.assertEqual(self.allow.load(bad)["mode"], "list")

    def test_list_mode_admits_only_the_named_numbers(self):
        p = self.policy(mode="list", allow_numbers=["+447700900123"])
        self.assertEqual(self.allow.decide("+44 7700 900123", p), (True, "on-the-list"))
        self.assertEqual(self.allow.decide("+447700900999", p), (False, "not-on-the-list"))

    def test_local_mode_uses_the_dial_code_of_the_home_country(self):
        p = self.policy(mode="local", home="GB")
        self.assertEqual(self.allow.decide("+447700900123", p), (True, "local"))
        self.assertEqual(self.allow.decide("+46701234567", p), (False, "not-local"))

    def test_local_with_no_home_country_admits_nobody(self):
        self.assertEqual(self.allow.decide("+447700900123", self.policy(mode="local")),
                         (False, "no-home-country"))

    def test_regions_mode_allows_some_countries_and_refuses_others(self):
        p = self.policy(mode="regions", allow_countries=["GB", "SE"], block_countries=["PL"])
        self.assertTrue(self.allow.decide("+447700900123", p)[0])
        self.assertTrue(self.allow.decide("+46701234567", p)[0])
        self.assertEqual(self.allow.decide("+48501234567", p), (False, "country-blocked"))
        self.assertEqual(self.allow.decide("+4915112345678", p), (False, "country-not-allowed"))

    def test_regions_mode_with_nothing_allowed_admits_nobody(self):
        self.assertEqual(self.allow.decide("+447700900123", self.policy(mode="regions")),
                         (False, "no-countries-allowed"))

    def test_a_blocked_country_beats_an_allowed_one_by_default(self):
        p = self.policy(mode="regions", allow_countries=["PL"], block_countries=["PL"])
        self.assertEqual(self.allow.decide("+48501234567", p), (False, "country-blocked"))

    def test_a_listed_number_gets_in_whatever_the_mode_says(self):
        p = self.policy(mode="local", home="GB", allow_numbers=["+46701234567"])
        self.assertEqual(self.allow.decide("+46701234567", p), (True, "on-the-list"))
        off = self.policy(mode="local", home="GB", allow_numbers=["+46701234567"], also_allow_list=False)
        self.assertEqual(self.allow.decide("+46701234567", off), (False, "not-local"))

    def test_a_blocked_number_loses_even_when_it_is_listed(self):
        p = self.policy(mode="open", allow_numbers=["+447700900123"], block_numbers=["+447700900123"])
        self.assertEqual(self.allow.decide("+447700900123", p), (False, "number-blocked"))

    def test_block_wins_can_be_turned_off_for_countries(self):
        p = self.policy(mode="open", block_countries=["PL"], block_wins=False)
        self.assertTrue(self.allow.decide("+48501234567", p)[0])

    def test_a_listed_number_survives_a_blocked_country_only_when_block_wins_is_off(self):
        on = self.policy(mode="list", allow_numbers=["+48501234567"], block_countries=["PL"])
        self.assertEqual(self.allow.decide("+48501234567", on), (False, "country-blocked"))
        off = self.policy(mode="list", allow_numbers=["+48501234567"], block_countries=["PL"], block_wins=False)
        self.assertEqual(self.allow.decide("+48501234567", off), (True, "on-the-list"))

    def test_the_longest_dial_code_wins(self):
        self.assertEqual(self.allow.country_of("+37061234567"), "LT", "+370 is lithuania, not a +3 anything")
        self.assertEqual(self.allow.country_of("+447700900123"), "GB")
        self.assertEqual(self.allow.country_of("+919876543210"), "IN")

    def test_plus_one_is_one_plan_and_the_file_says_so(self):
        self.assertEqual(self.allow.country_of("+14155550123"), "NANP")
        self.assertEqual(self.allow.country_of("+16475550123"), "NANP", "toronto looks the same as san francisco")
        for name in ("united states", "usa", "canada"):
            self.assertEqual(self.allow.region(name), "NANP")
        self.assertIn("us-only-from-a-plus-one", self.allow.REFUSED)

    def test_a_number_the_table_cannot_place_is_refused_by_every_region_rule(self):
        stranger = "+99912345678"
        self.assertIsNone(self.allow.country_of(stranger))
        self.assertEqual(self.allow.decide(stranger, self.policy(mode="regions", allow_countries=["GB"])),
                         (False, "country-unknown"))
        self.assertEqual(self.allow.decide(stranger, self.policy(mode="local", home="GB")),
                         (False, "country-unknown"))

    def test_open_mode_exists_but_is_never_the_default(self):
        self.assertIn("open", self.allow.MODES)
        self.assertTrue(self.allow.decide("+447700900123", self.policy(mode="open"))[0])
        self.assertNotEqual(self.allow.default_policy()["mode"], "open")

    def test_a_garbage_sender_is_refused_in_every_mode(self):
        for mode in self.allow.MODES:
            for junk in (None, "", "not a number", "+0123456", "this is far too long to be a sender",
                         ["+447700900123"], b"+447700900123", 1234567890123456789,
                         "+\uff14\uff14\uff17\uff17\uff10\uff10\u2079\uff10\uff10\uff11\uff12\uff13"):
                self.assertFalse(self.allow.decide(junk, self.policy(mode=mode))[0], f"{mode} admitted {junk!r}")

    def test_a_short_code_or_brand_name_gets_in_only_through_open(self):
        """a verification text comes from AMAZON or 12345, which have no country. only open can vouch for one."""
        for name in ("AMAZON", "VM-BANK", "12345"):
            self.assertEqual(self.allow.decide(name, self.policy(mode="open")), (True, "open-name"))
            for mode in ("list", "local", "regions"):
                p = self.policy(mode=mode, home="GB", allow_countries=["GB"], allow_numbers=["+447700900123"])
                self.assertEqual(self.allow.decide(name, p), (False, "alphanumeric-sender"),
                                 f"{mode} admitted {name!r}, which has no country to check")

    def test_a_name_is_refused_under_its_own_reason_not_as_a_malformed_number(self):
        self.assertEqual(self.allow.decide("AMAZON", self.policy(mode="list"))[1], "alphanumeric-sender")
        self.assertEqual(self.allow.decide("not a number", self.policy(mode="list"))[1], "no-number")
        self.assertIn("name-as-a-number", self.allow.REFUSED)

    def test_a_blocked_name_stays_out_even_in_open_mode(self):
        p = self.policy(mode="open", block_numbers=["amazon"])
        self.assertEqual(self.allow.decide("AMAZON", p), (False, "alphanumeric-sender"))

    def test_bare_digits_are_a_number_only_when_they_start_with_a_known_dial_code(self):
        """some carriers drop the plus. 447700900123 is a uk number, 123456789012 is just digits."""
        self.assertEqual(self.allow.normalize_number("447700900123"), "+447700900123")
        self.assertEqual(self.allow.normalize_number("919876543210"), "+919876543210")
        self.assertIsNone(self.allow.normalize_number("999123456789"), "no dial code starts this")
        listed = self.policy(mode="list", allow_numbers=["+447700900123"])
        self.assertEqual(self.allow.decide("447700900123", listed), (True, "on-the-list"),
                         "a listed sender was locked out because the carrier dropped the plus")

    def test_a_unicode_digit_anywhere_in_a_number_is_refused(self):
        """\\d matches fullwidth and arabic-indic digits in python, so a number that starts with an ascii digit
        and continues in fullwidth passes `[1-9]\\d{6,14}`. the leading digit hid it for the pure case."""
        fullwidth = lambda s: "".join(chr(0xFF10 + int(d)) for d in s)
        arabic = lambda s: "".join(chr(0x0660 + int(d)) for d in s)
        for sneaky in ("+" + fullwidth("447700900123"),
                       "+4" + fullwidth("47700900123"),
                       "+44770090" + fullwidth("0123"),
                       "+4" + arabic("47700900123"),
                       fullwidth("447700900123")):
            self.assertIsNone(self.allow.normalize_number(sender := sneaky), f"accepted {sneaky!r}")
            self.assertFalse(self.allow.decide(sender, self.policy(mode="open"))[0],
                             f"open mode admitted a number made of unicode digits: {sneaky!r}")
        self.assertEqual(self.allow.normalize_number("+447700900123"), "+447700900123", "the real one still works")

    def test_the_e164_pattern_is_ascii_digits_and_a_fullmatch(self):
        self.assertNotIn("\\d", self.allow.E164.pattern, "\\d is unicode aware in python")
        self.assertIsNone(self.allow.E164.fullmatch("+447700900123\n"), "a trailing newline is not a number")
        self.assertTrue(self.allow.E164.fullmatch("+447700900123"))

    def test_every_edit_says_what_it_changed_and_refuses_what_it_cannot_do(self):
        p = self.allow.default_policy()
        p, note = self.allow.apply(p, "mode", "regions")
        self.assertEqual(note["changed"], "mode list -> regions")
        p, note = self.allow.apply(p, "allow-country", "United Kingdom")
        self.assertEqual(p["allow_countries"], ["GB"])
        p, note = self.allow.apply(p, "allow-country", "uk")
        self.assertEqual(p["allow_countries"], ["GB"], "adding twice must not duplicate")
        p, note = self.allow.apply(p, "block-country", "atlantis")
        self.assertFalse(note["ok"])
        p, note = self.allow.apply(p, "mode", "everyone")
        self.assertFalse(note["ok"])
        p, note = self.allow.apply(p, "allow", "07700 900123")
        self.assertFalse(note["ok"], "a number without a country code is not an e164 number")
        p, note = self.allow.apply(p, "unallow-country", "gb")
        self.assertEqual(p["allow_countries"], [])

    def test_the_policy_file_is_written_private_and_round_trips(self):
        target = self.tmp / "allow.json"
        p, _ = self.allow.apply(self.allow.default_policy(), "mode", "local")
        p, _ = self.allow.apply(p, "home", "india")
        self.allow.save(p, target)
        self.assertEqual(oct(target.stat().st_mode & 0o777), "0o600")
        again = self.allow.load(target)
        self.assertEqual((again["mode"], again["home"]), ("local", "IN"))

    def test_explain_says_it_in_a_sentence_a_person_can_check(self):
        self.assertIn("only the 0 numbers", self.allow.explain(self.allow.default_policy()))
        text = self.allow.explain(self.policy(mode="regions", allow_countries=["GB", "SE"], block_countries=["PL"]))
        self.assertIn("GB, SE", text)
        self.assertIn("never PL", text)
        self.assertIn("no home country", self.allow.explain(self.policy(mode="local")))

    def test_a_refusal_is_logged_without_the_text_or_the_whole_number(self):
        log = self.tmp / "refused.jsonl"
        self.allow.record_refusal("+447700900123", "not-on-the-list", log, at=1000)
        row = json.loads(log.read_text().strip())
        self.assertEqual(row["why"], "not-on-the-list")
        self.assertEqual(row["region"], "GB")
        self.assertNotIn("7700900", row["sender"], "the log must not rebuild a contact list")
        self.assertNotIn("body", row)
        self.assertEqual(oct(log.stat().st_mode & 0o777), "0o600")
        summary = self.allow.refusal_summary(log)
        self.assertEqual(summary["refused"], 1)
        self.assertEqual(summary["by_region"], {"GB": 1})

    def test_the_catcher_stores_an_allowed_text_and_refuses_the_rest_before_the_inbox(self):
        from src.manage import catcher, inbox
        import threading
        import urllib.request
        from http.server import HTTPServer

        store = self.tmp / "inbox.jsonl"
        refused = self.tmp / "refused.jsonl"
        pol = self.policy(mode="list", allow_numbers=["+447700900123"])
        server = HTTPServer(("127.0.0.1", 0), catcher.make_handler(None, str(store), pol, str(refused)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/"

            def post(sender, ident):
                req = urllib.request.Request(url, data=json.dumps(
                    {"from": sender, "to": "+15550001111", "body": "hi", "id": ident}).encode(),
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as reply:
                    return reply.status, json.loads(reply.read())

            status, body = post("+447700900123", "m1")
            self.assertEqual((status, body["stored"]), (200, True))
            status, body = post("+46701234567", "m2")
            self.assertEqual(status, 200, "a refusal must not look like an error to a carrier that retries")
            self.assertFalse(body["stored"])
            self.assertEqual((body["reason"], body["why"]), ("refused", "not-on-the-list"))
            rows = inbox.read(str(store))
            self.assertEqual([r.get("id") for r in rows], ["m1"], "the refused text reached the inbox")
            self.assertEqual(self.allow.refusal_summary(refused)["refused"], 1)
        finally:
            server.shutdown()
            server.server_close()

    def test_an_edit_takes_effect_on_the_next_text_without_a_restart(self):
        from src.manage import catcher
        import threading
        import urllib.request
        from http.server import HTTPServer

        cfg = self.tmp / "live.json"
        os.environ["HEYPHONY_ALLOW"] = str(cfg)
        store = self.tmp / "live-inbox.jsonl"
        server = HTTPServer(("127.0.0.1", 0), catcher.make_handler(None, str(store), None,
                                                                   str(self.tmp / "live-refused.jsonl")))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/"

            def post(ident):
                req = urllib.request.Request(url, data=json.dumps(
                    {"from": "+447700900123", "to": "+15550001111", "body": "hi", "id": ident}).encode(),
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as reply:
                    return json.loads(reply.read())

            self.assertFalse(post("a")["stored"], "the unset policy must start closed")
            opened, _ = self.allow.apply(self.allow.default_policy(), "allow", "+447700900123")
            self.allow.save(opened, cfg)
            self.assertTrue(post("b")["stored"], "an edit did not reach the running catcher")
            closed, _ = self.allow.apply(opened, "block", "+447700900123")
            self.allow.save(closed, cfg)
            self.assertFalse(post("c")["stored"], "a block did not reach the running catcher")
        finally:
            os.environ.pop("HEYPHONY_ALLOW", None)
            server.shutdown()
            server.server_close()

    def test_the_command_edits_shows_and_checks(self):
        env = dict(os.environ, HEYPHONY_ALLOW=str(self.tmp / "cli.json"), XDG_DATA_HOME=str(self.tmp / "data"))

        def run(*args):
            return subprocess.run([str(ROOT / "bin" / "heyphony"), "allow", *args], capture_output=True,
                                  text=True, timeout=60, env=env)

        shown = run()
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertEqual(json.loads(shown.stdout)["policy"]["mode"], "list")
        self.assertEqual(run("mode", "local").returncode, 0)
        self.assertEqual(run("home", "uk").returncode, 0)
        inside, outside = run("check", "+447700900123"), run("check", "+46701234567")
        self.assertEqual((inside.returncode, outside.returncode), (0, 1), "check must exit by its answer")
        self.assertEqual(json.loads(inside.stdout)["why"], "local")
        self.assertEqual(run("block-country", "atlantis").returncode, 2)

    def test_the_pages_carry_it(self):
        page = (ROOT / "readme.md").read_text()
        for needle in ("and who it will hear from is a setting, not a hope", "an unset one admits nobody",
                       "a broken policy file shuts the door", "**a list.**", "**local.**",
                       "**chosen countries.**", "north american numbering plan", "never the text"):
            self.assertIn(needle, page, f"the readme lost {needle!r}")
        self.assertIn("`heyphony allow`", (ROOT / "src/setup/commands/readme.md").read_text())
        self.assertIn("who gets in, before anything", (ROOT / "src/manage/readme.md").read_text())
        for path in (ROOT / "src/manage/allow.py", ROOT / "readme.md", ROOT / "src/manage/readme.md"):
            self.assertNotIn("\u2014", path.read_text(), f"{path.name} has an em dash")


class TestTheBranchIndexMatchesGit(unittest.TestCase):
    """repo.md says which branches mcp already contains, so git is asked instead of the page being trusted."""

    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / "repo.md").read_text()
        cls.rows = {}
        for line in cls.page.splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == 3 and cells[0].startswith("`") and cells[0].endswith("`"):
                cls.rows[cells[0].strip("`")] = cells[2]

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=60)

    def remote_branches(self):
        out = self.git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin")
        if out.returncode != 0:
            return []
        return sorted(n.split("/", 1)[1] for n in out.stdout.split() if "/" in n and not n.endswith("/HEAD"))

    def test_mcp_is_in_the_index_and_says_it_is_flat(self):
        self.assertIn("mcp", self.rows, "the mcp branch is missing from the index")
        self.assertIn("this is it", self.rows["mcp"])
        self.assertIn("no `mcp/` folder", self.page)
        self.assertFalse((ROOT / "mcp").exists(), "mcp is a branch, not a folder")

    def test_main_is_not_merged_into_mcp_and_the_page_says_why(self):
        self.assertIn("is deliberately not merged into it", " ".join(self.page.split()))
        self.assertIn("never appears on the page", self.page)

    def test_every_row_is_a_known_cell(self):
        for name, cell in self.rows.items():
            self.assertIn(cell, ("yes", "no", "this is it"), f"{name} has an unreadable last cell: {cell!r}")

    def test_the_page_matches_the_branches_git_has(self):
        branches = self.remote_branches()
        if "mcp" not in branches:
            self.skipTest("this copy has no origin/mcp ref to compare against")
        self.assertEqual(sorted(self.rows), branches,
                         "a branch exists that repo.md does not list, or the reverse")

    def test_the_last_column_is_read_from_git(self):
        branches = self.remote_branches()
        if "mcp" not in branches:
            self.skipTest("this copy has no origin/mcp ref to compare against")
        # the page is committed on mcp, so mcp itself is compared by its own head
        for name in branches:
            if name == "mcp":
                continue
            inside = self.git("merge-base", "--is-ancestor", f"origin/{name}", "origin/mcp").returncode == 0
            self.assertEqual(self.rows[name], "yes" if inside else "no",
                             f"{name}: the page says {self.rows[name]!r} but git says {'yes' if inside else 'no'}")

    def test_no_em_dash(self):
        self.assertNotIn("\u2014", self.page)


class TestThePypiPackageIsTheRepoRenamed(unittest.TestCase):
    """the pypi build copies src/ to heyphony/ and rewrites imports. the claims worth pinning are the
    ones that would go wrong silently: a leaked top-level `src`, a second version, a dirty tree."""

    @classmethod
    def setUpClass(cls):
        cls.pypi = ROOT / "pypi"
        cls.script = cls.pypi / "build.py"
        spec = importlib.util.spec_from_file_location("pypi_build", cls.script)
        cls.build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.build)

    def test_import_rewrite_covers_both_statement_forms(self):
        text = "from src.setup import routes\nimport src\n    from src import providers\nx = 'src.not an import'\n"
        out = self.build.rewrite(text)
        self.assertIn("from heyphony.setup import routes", out)
        self.assertIn("import heyphony\n", out)
        self.assertIn("    from heyphony import providers", out)
        self.assertIn("'src.not an import'", out, "a string that merely mentions src must be left alone")

    def test_no_import_in_the_repo_is_missed_by_the_rewrite(self):
        for path in (ROOT / "src").rglob("*.py"):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                stripped = line.strip()
                if re.match(r"(from|import)\s+src\b", stripped):
                    self.assertTrue(self.build.IMPORT.match(line),
                                    f"{path.relative_to(ROOT)}:{number} is an src import the rewrite would miss")

    def test_the_version_has_one_source(self):
        self.assertEqual(self.build.version(), json.loads((ROOT / "npm/package.json").read_text())["version"])
        toml = (self.pypi / "pyproject.toml").read_text()
        self.assertIn("dynamic = [\"version\"]", toml)
        self.assertNotRegex(toml, r"(?m)^version\s*=\s*[\"']\d", "pyproject must read the version, never state one")

    def test_the_console_script_points_at_a_real_main(self):
        toml = (self.pypi / "pyproject.toml").read_text()
        self.assertIn('heyphony = "heyphony.runner.cli:main"', toml)
        self.assertRegex((ROOT / "src/runner/cli.py").read_text(), r"(?m)^def main\(argv=None\)")

    def test_a_build_leaves_no_src_package_and_cleans_up(self):
        import tempfile
        before = sorted(p.name for p in self.pypi.iterdir())
        try:
            self.build.build()
            out = self.pypi / "heyphony"
            self.assertTrue((out / "runner" / "cli.py").exists())
            self.assertFalse((out / "src").exists(), "a nested src/ would mean the copy kept the old root")
            for path in out.rglob("*.py"):
                self.assertNotRegex(path.read_text(), r"(?m)^\s*(from|import)\s+src\b",
                                    f"{path.relative_to(self.pypi)} still imports src")
            self.assertTrue((out / "lookup" / "nanp.json").exists(), "the data a module reads by __file__ must travel")
        finally:
            self.build.clean()
        self.assertEqual(sorted(p.name for p in self.pypi.iterdir()), before,
                         "the build left generated files in a tree that has no .gitignore")

    def test_the_build_does_not_touch_the_repo_source(self):
        before = subprocess.run(["git", "status", "--porcelain", "src"], cwd=ROOT, capture_output=True, text=True).stdout
        try:
            self.build.build()
        finally:
            self.build.clean()
        after = subprocess.run(["git", "status", "--porcelain", "src"], cwd=ROOT, capture_output=True, text=True).stdout
        self.assertEqual(before, after)

    def test_the_readme_does_not_claim_pip_works_until_it_does(self):
        """the page says what is true. while nothing is uploaded it must say so, and npm stays first."""
        text = (ROOT / "readme.md").read_text()
        self.assertIn("pypi/publish.md", text)
        self.assertLess(text.index("npm i -g heyphony"), text.index("pypi/publish.md"),
                        "npm is the first route and the page must keep leading with it")
        runbook = (self.pypi / "publish.md").read_text()
        uploaded = "pip install heyphony" not in text.split("not uploaded yet")[0] and "not uploaded yet" in text
        self.assertTrue(uploaded or "pip install heyphony" in text,
                        "the page neither says pypi is unpublished nor how to install from it")
        self.assertIn("nothing has been uploaded", runbook)
        self.assertEqual(("not uploaded yet" in text), ("nothing has been uploaded" in runbook),
                         "the readme and the runbook disagree about whether it is published")

    def test_the_floor_is_python_3_8_and_the_code_keeps_to_it(self):
        """requires-python says 3.8, and so does the npm shim. a grammar check alone missed the dict
        union operator (3.9) that broke anveo provisioning, so this also reads for what only fails at run time."""
        import ast
        self.assertIn('requires-python = ">=3.8"', (self.pypi / "pyproject.toml").read_text())
        late = [
            (r"\.removeprefix\(|\.removesuffix\(", "str.removeprefix (3.9)"),
            (r"\bzip\([^)]*strict\s*=", "zip(strict=) (3.10)"),
            (r"^\s*match\s+\S.*:\s*$", "match statement (3.10)"),
            (r"(?:->|:)\s*(?:list|dict|tuple|set|frozenset)\[", "builtin generic annotation (3.9)"),
            (r"(?:->|:)\s*\w+\s*\|\s*None", "X | None annotation (3.10)"),
            (r"\bint\.bit_count\(|\.bit_count\(\)", "int.bit_count (3.10)"),
            (r"^[^\"']*\bdict\([^()]*\)\s*\|\s*[{d]|^[^\"']*\}\s*\|\s*\{", "dict union operator (3.9)"),
        ]
        for path in (ROOT / "src").rglob("*.py"):
            text = path.read_text()
            try:
                ast.parse(text, feature_version=(3, 8))
            except SyntaxError as error:
                self.fail(f"{path.relative_to(ROOT)}:{error.lineno} does not parse as python 3.8: {error.msg}")
            for number, line in enumerate(text.splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                for pattern, name in late:
                    if re.search(pattern, line):
                        self.fail(f"{path.relative_to(ROOT)}:{number} uses {name}, newer than the 3.8 floor: {line.strip()}")

    def test_no_em_dash(self):
        self.assertNotIn("\u2014", self.script.read_text())

class TestBothRailsAtOnce(unittest.TestCase):
    """one number, a call in progress and a text arriving on it, in the same second.

    the fake far end is a socketpair: the far side writes what baresip writes (its own documented
    event names, netstring framed), and the rail under test reads it exactly as it would read the
    real socket. the text side is a *real* http server on an ephemeral port, because the catcher is
    the code being trusted and stubbing it would test the stub.
    """

    def setUp(self):
        from src.live import both
        self.both = both
        self.session_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.session_dir, True)

    def open_to(self, numbers):
        """the policy shape allow.decide actually reads: a mode and a list, not an allow/refuse pair."""
        return {"mode": "list", "allow_numbers": list(numbers)}

    def wire(self, policy=None):
        """a session whose call socket is one end of a socketpair and whose webhook is real."""
        near, far = socket.socketpair()
        self.addCleanup(near.close)
        self.addCleanup(far.close)
        timeline = self.both.Timeline()
        call = self.both.CallRail(timeline, sock=near)
        call.open = True
        inbox = self.both.InboxRail(timeline, port=0, path=os.path.join(self.session_dir, "inbox.jsonl"),
                                    policy=policy or self.open_to(["+15550000001"]))
        inbox.start()
        self.addCleanup(inbox.stop)
        return {"near": near, "far": far, "timeline": timeline, "call": call, "inbox": inbox}

    def say(self, far, event, **fields):
        payload = {"event": "true", "class": "call", "type": event}
        payload.update(fields)
        far.sendall(self.both.netstring(payload))

    def text(self, port, body, sender="+15550000001", **extra):
        # flowroute's documented webhook body: lowercase from/to/body, posted to /sms/flowroute
        payload = {"from": sender, "to": "+15550000002", "body": body, "id": f"m{time.time_ns()}"}
        payload.update(extra)
        request = urllib.request.Request(f"http://127.0.0.1:{port}/sms/flowroute",
                                         data=json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read())

    def test_a_text_lands_while_the_call_is_still_up(self):
        """the actual question: on a call, somebody sends a picture instead of explaining.

        asserted as an order, not as two separate arrivals, because "at the same time" only means
        something if the log can say the text came after the call was answered and before it ended.
        """
        wired = self.wire()
        self.say(wired["far"], "CALL_ESTABLISHED", peeruri="sip:ada@example.net", id="c1")
        self.assertEqual(wired["call"].read_once()[0]["what"], "answered, both ways are open")
        self.text(wired["inbox"].port, "just sent you the screenshot",
                  media=["https://carrier.example/m/9.jpg"])
        self.say(wired["far"], "CALL_CLOSED", peeruri="sip:ada@example.net", id="c1")
        read = wired["call"].read_once()
        self.assertEqual([e["what"] for e in read], ["hung up"])

        order = [e["what"] for e in wired["timeline"].events()]
        self.assertEqual(order, ["webhook listening", "answered, both ways are open",
                                 "text arrived", "hung up"],
                         "the three events have to be one ordered log, or nothing can be said about "
                         "what the caller meant by 'just sent it'")
        arrived = wired["timeline"].first("sms", "text arrived")
        self.assertEqual(arrived["media"], ["https://carrier.example/m/9.jpg"])
        self.assertEqual(arrived["sender"], "+15550000001")
        # the text arrived inside the call, which is the whole claim
        answered = wired["timeline"].first("call", "answered, both ways are open")
        closed = wired["timeline"].first("call", "hung up")
        self.assertLess(answered["seq"], arrived["seq"])
        self.assertLess(arrived["seq"], closed["seq"])

    def test_the_stored_message_keeps_the_media_urls(self):
        wired = self.wire()
        self.text(wired["inbox"].port, "look at this",
                  media=["https://c.example/1.jpg", "https://c.example/2.png"])
        stored = inbox.read(os.path.join(self.session_dir, "inbox.jsonl"))
        self.assertEqual(stored[-1]["media"], ["https://c.example/1.jpg", "https://c.example/2.png"])

    def test_neither_rail_waits_for_the_other(self):
        """two rails on one thread would pass the ordering test above while still being useless."""
        wired = self.wire()
        stop = {"at": time.time() + 3}
        reader = threading.Thread(target=wired["call"].pump,
                                  kwargs={"answer_on_incoming": False,
                                          "stop": lambda: time.time() > stop["at"]})
        reader.start()
        try:
            for i in range(6):
                self.text(wired["inbox"].port, f"message {i}")
                self.say(wired["far"], "CALL_ESTABLISHED", id=f"c{i}")
                time.sleep(0.05)
        finally:
            stop["at"] = 0
            reader.join(timeout=3)
        self.assertFalse(reader.is_alive(), "the pump did not notice it was told to stop")
        texts = wired["timeline"].events("sms")
        self.assertEqual(len([e for e in texts if e["what"] == "text arrived"]), 6,
                         "a webhook was dropped while the call socket was being read")
        self.assertGreaterEqual(len(wired["timeline"].events("call")), 6)

    def test_two_webhooks_are_served_at_once_not_one_after_the_other(self):
        """the catcher was a single thread, so a slow carrier could hold the door while a call was up.

        proved by making the store slow: three posts that each take 0.4s finish in about one of
        them when the server threads, and in three of them when it does not.
        """
        wired = self.wire()
        real = inbox.append
        calls = []

        def slow(entry, path=None):
            calls.append(entry.get("body"))
            time.sleep(0.4)
            return real(entry, path)

        inbox.append = slow
        self.addCleanup(setattr, inbox, "append", real)
        started = time.time()
        threads = [threading.Thread(target=self.text, args=(wired["inbox"].port, f"n{i}"))
                   for i in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=6)
        took = time.time() - started
        self.assertEqual(sorted(calls), ["n0", "n1", "n2"], "a webhook was lost")
        self.assertLess(took, 1.0, f"three posts took {took:.2f}s, so they queued behind each other")

    def test_a_refused_sender_is_still_news_on_the_log(self):
        wired = self.wire(policy=self.open_to(["+15550000001"]))
        answer = self.text(wired["inbox"].port, "hello", sender="+15559999999")
        self.assertEqual(answer.get("stored"), False)
        refused = wired["timeline"].first("sms", "text refused")
        self.assertIsNotNone(refused, "the rail went quiet about a sender it refused")
        self.assertEqual(refused["sender"], "+15559999999")
        self.assertIn("refused", refused["reason"])

    def test_answering_is_one_command_over_the_same_socket(self):
        wired = self.wire()
        self.say(wired["far"], "CALL_INCOMING", peeruri="sip:ada@example.net", id="c9")
        wired["far"].settimeout(2)
        read = wired["call"].read_once()
        self.assertEqual(read[0]["what"], "ringing at this number")
        self.assertTrue(wired["call"].answer()["ok"])
        sent, rest = self.both.decode(wired["far"].recv(4096))
        self.assertEqual(sent[0]["command"], "answer")
        self.assertEqual(sent[0]["params"], "", "baresip takes params as a string, empty here")

    def test_the_wait_is_woken_by_the_rail_that_speaks(self):
        wired = self.wire()
        started = time.time()
        seen = {}

        def post():
            time.sleep(0.15)
            self.text(wired["inbox"].port, "sent it")

        threading.Thread(target=post, daemon=True).start()
        event = wired["timeline"].next_event(timeout=3)
        seen["event"] = event
        self.assertIsNotNone(event, "a wait that watches both rails timed out on a text")
        self.assertEqual(event["rail"], "sms")
        self.assertLess(time.time() - started, 3)

    def test_the_wait_ignores_a_rail_it_was_not_asked_for(self):
        wired = self.wire()
        seen = wired["timeline"].events()[-1]["seq"]
        wired["timeline"].add("call", "socket open")
        self.assertIsNone(wired["timeline"].next_event(since=seen, rails=("sms",), timeout=0.3))
        self.assertEqual(wired["timeline"].next_event(since=seen, rails=("call",), timeout=0.3)["what"],
                         "socket open")

    def test_the_protocol_is_read_the_way_baresip_writes_it(self):
        wired = self.wire()
        body = self.both.netstring({"event": "true", "class": "call", "type": "CALL_RINGING",
                                    "peeruri": "sip:ada@example.net", "id": "c1"})
        wired["far"].sendall(body[:7])
        time.sleep(0.05)
        self.assertEqual(wired["call"].read_once(), [], "a half netstring is not an event yet")
        wired["far"].sendall(body[7:])
        time.sleep(0.05)
        self.assertEqual(wired["call"].read_once()[0]["what"], "ringing at the far end")

    def test_a_bare_json_event_is_baresips_own_example(self):
        wired = self.wire()
        wired["far"].sendall(b'{"event":"true","class":"call","type":"CALL_CLOSED"}')
        time.sleep(0.05)
        self.assertEqual(wired["call"].read_once()[0]["what"], "hung up")

    def test_the_plan_states_what_was_not_proven(self):
        plan = self.both.plan()
        self.assertTrue(plan["shipped"])
        joined = " ".join(plan["not_included"])
        self.assertIn("no registration", joined)
        self.assertIn("a real carrier", joined)
        self.assertEqual(self.both.plan()["rails"]["sms"][:14], "the catcher, n")


class TestTheScreenshotIsReachable(unittest.TestCase):
    """an mms is a text plus urls on somebody else's server, so the claim is three small ones."""

    def setUp(self):
        from src.manage import media
        from src.setup import routes
        self.media = media
        self.routes = routes
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def serve(self, body, content_type="image/png", status=200):
        """a real http server, because the fetch path is the code under test."""
        class Handler(SimpleHTTPRequestHandler):
            def do_GET(self):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server.server_address[1]

    def test_three_carrier_shapes_and_a_nested_one_all_keep_their_urls(self):
        one = [
            {"media": ["https://c/a.jpg"]},
            {"attachments": [{"url": "https://c/a.jpg"}]},
            {"wrapper": {"media": [{"MediaUrl": "https://c/a.jpg"}]}},
        ]
        for shape in one:
            self.assertEqual(self.routes.media_of(shape), ["https://c/a.jpg"],
                             f"{shape} did not yield its url")
        # a comma string is one carrier's whole answer, so both urls survive and in order
        self.assertEqual(self.routes.media_of({"MediaUrls": "https://c/a.jpg, https://c/b.png"}),
                         ["https://c/a.jpg", "https://c/b.png"])

    def test_a_text_with_no_media_says_so_with_an_empty_list(self):
        entry = phone_catcher.normalize({"from": "+1555", "body": "no pictures"})
        self.assertEqual(entry["media"], [])

    def test_a_picture_is_fetched_and_named_for_its_type(self):
        port = self.serve(b"\x89PNG\r\n\x1a\n" + b"0" * 40)
        got = self.media.fetch(f"http://127.0.0.1:{port}/x", self.dir, message_id="m1")
        self.assertTrue(got["ok"], got.get("why"))
        self.assertTrue(got["path"].endswith("m1-0.png"))
        self.assertEqual(got["bytes"], 48)
        self.assertTrue(os.path.exists(got["path"]))

    def test_a_url_that_is_not_http_is_refused_by_name(self):
        got = self.media.fetch("file:///etc/passwd", self.dir)
        self.assertFalse(got["ok"])
        self.assertIn("fetch-the-whole-internet", got["why"])

    def test_something_too_big_is_refused_and_leaves_nothing_behind(self):
        port = self.serve(b"0" * 5000)
        got = self.media.fetch(f"http://127.0.0.1:{port}/x", self.dir, max_bytes=1000)
        self.assertFalse(got["ok"])
        self.assertIn("a-picture-of-any-size", got["why"])
        self.assertEqual(os.listdir(self.dir), [], "a partial file stayed on disk")

    def test_a_type_that_is_not_a_picture_is_not_named_as_one(self):
        port = self.serve(b"<html>", content_type="text/html")
        got = self.media.fetch(f"http://127.0.0.1:{port}/x", self.dir)
        self.assertFalse(got["ok"])
        self.assertIn("read-as-an-image-what-is-not", got["why"])

    def test_a_carrier_that_wants_a_login_is_reported_as_one(self):
        port = self.serve(b"nope", status=401)
        got = self.media.fetch(f"http://127.0.0.1:{port}/x", self.dir)
        self.assertFalse(got["ok"])
        self.assertIn("401", got["why"])
        self.assertIn("login", got["why"])

    def test_a_message_with_two_pictures_reports_two_results(self):
        port = self.serve(b"\x89PNG\r\n\x1a\n" + b"0" * 8)
        entry = {"id": "m7", "sender": "+1555",
                 "media": [f"http://127.0.0.1:{port}/1", "file:///nope"]}
        got = self.media.fetch_all(entry, self.dir)
        self.assertEqual(len(got["results"]), 2)
        self.assertEqual(len(got["kept"]), 1)
        self.assertEqual(got["failed"], ["file:///nope"])
        self.assertTrue(got["kept"][0].endswith("m7-0.png"))

    def test_the_plan_says_fetching_is_not_reading(self):
        plan = self.media.plan()
        self.assertTrue(plan["shipped"])
        self.assertIn("not describing it", " ".join(plan["not_included"]))
        self.assertIn("a-picture-of-any-size", plan["refused"])


class TestTheLiveVerbAndTheScreenshotCommand(unittest.TestCase):
    """the two verbs the multi-rail work is reachable from, and the prose that limits them."""

    def run_cli(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = telephony_cli.main(argv)
        return code, out.getvalue()

    def test_live_prints_the_plan_and_the_part_that_is_not_proven(self):
        code, out = self.run_cli(["live"])
        plan = json.loads(out)
        self.assertEqual(code, 0)
        self.assertTrue(plan["shipped"])
        self.assertIn("no registration", " ".join(plan["not_included"]))
        self.assertIn("one-rail-at-a-time", plan["refused"])

    def test_media_with_no_url_says_what_to_pass(self):
        code, out = self.run_cli(["media", "fetch"])
        self.assertEqual(code, 2)
        self.assertIn("--url", json.loads(out)["why"])

    def test_an_omitted_cap_is_still_a_cap(self):
        """the flag defaults to None, and a None cap is no cap: the download path must fill it in."""
        from src.manage import media

        class Big(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(media.MAX_BYTES + 1))
                self.end_headers()
                self.wfile.write(b"0" * (media.MAX_BYTES + 1))

            def log_message(self, *a):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Big)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        code, out = self.run_cli(["media", "fetch", "--url",
                                  f"http://127.0.0.1:{server.server_address[1]}/big", "--into", folder])
        self.assertEqual(code, 1)
        self.assertIn("a-picture-of-any-size", json.loads(out)["why"])
        self.assertEqual(os.listdir(folder), [])

    def test_media_refuses_a_url_that_is_not_http_through_the_cli(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        code, out = self.run_cli(["media", "fetch", "--url", "file:///etc/passwd", "--into", folder])
        self.assertEqual(code, 1)
        self.assertIn("fetch-the-whole-internet", json.loads(out)["why"])
        self.assertEqual(os.listdir(folder), [])

    def test_the_readme_does_not_claim_a_carrier_proof(self):
        page = (ROOT / "readme.md").read_text()
        self.assertIn("### on a call while a text arrives", page)
        self.assertIn("not proven and are not claimed", page)
        self.assertIn("fetch-the-whole-internet", page)

    def test_the_live_page_names_both_doors(self):
        page = (ROOT / "src/live/readme.md").read_text()
        self.assertIn("ctrl_tcp", page)
        self.assertIn("ThreadingHTTPServer", page)
        self.assertIn("not proven", page)

    def test_no_page_picked_up_an_em_dash(self):
        for name in ("readme.md", "src/live/readme.md"):
            self.assertNotIn("\u2014", (ROOT / name).read_text(), name)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    failed = len(result.failures) + len(result.errors)
    print(f"selftest: {result.testsRun - failed}/{result.testsRun} pass")
    sys.exit(1 if failed else 0)
