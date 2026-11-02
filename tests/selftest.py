"""meetings selftests: stdlib only. run: python3 tests/selftest.py

the branch is a contract, so the failures worth catching are prose drifting from `rails.py`, a rail
claiming a signature it does not have, and anything that quietly turns on a recording.
"""
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import rails  # noqa: E402


class TestTheRailsAreData(unittest.TestCase):
    def test_every_rail_carries_the_facts_a_join_needs(self):
        for name, row in rails.RAILS.items():
            for key in ("name", "join", "signature", "audio", "screenshare", "gate", "state",
                        "refused", "scope"):
                self.assertIn(key, row, f"{name} is missing {key}")
            self.assertEqual(row["name"], name)
            self.assertTrue(row["gate"], f"{name} has no gate")
            self.assertIn(row["state"], rails.STATES)

    def test_nothing_claims_a_joined_meeting(self):
        self.assertEqual(rails.by_state("verified"), [])
        self.assertEqual(rails.by_state("designed"), [])

    def test_only_zoom_carries_a_signature(self):
        self.assertIsNotNone(rails.signature_of("zoom"))
        self.assertIsNone(rails.signature_of("googlemeet"))
        self.assertIsNone(rails.signature_of("teams"))

    def test_the_zoom_signature_is_the_one_the_docs_describe(self):
        signature = rails.signature_of("zoom")
        self.assertEqual(signature["alg"], "HS256")
        self.assertIn("sdkKey", signature["payload"])
        self.assertIn("mn", signature["payload"])
        self.assertIn("minus 30 seconds", signature["why_backdated"])
        self.assertIn("tokenExp", signature["payload"])


class TestThePageMatchesTheData(unittest.TestCase):
    page = ROOT / "readme.md"

    def test_every_rail_is_on_the_page(self):
        text = self.page.read_text()
        for name, join, signature, audio, state in rails.table_rows():
            self.assertIn(f"`{name}`", text, f"the page does not list {name}")
            self.assertIn(audio, text, f"the page does not name {name}'s audio path")

    def test_the_page_admits_it_is_a_contract(self):
        text = self.page.read_text()
        self.assertIn("state is `contract` on every row", text)
        self.assertIn("nothing on this branch joins a meeting yet", text)

    def test_the_page_names_the_rename(self):
        text = self.page.read_text()
        self.assertIn("used to be called `omnimeetings`", text)
        self.assertIn("# meetings", text)

    def test_the_three_human_acts_are_on_the_page(self):
        text = self.page.read_text()
        for needle in ("sends the invite", "stays in the loop on recording",
                       "decides what the agent is for"):
            self.assertIn(needle, text, f"the page lost {needle!r}")

    def test_the_refusals_are_named(self):
        text = self.page.read_text()
        for needle in ("no cold joins", "no recording by default", "no broadcast"):
            self.assertIn(needle, text, f"the page lost {needle!r}")


class TestTheBranchStaysDecoupled(unittest.TestCase):
    def test_no_carrier_sdk_is_imported(self):
        allowed = {"pathlib", "sys", "unittest", "rails"}
        for path in sorted(ROOT.rglob("*.py")):
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")):
                    module = stripped.split()[1].split(".")[0]
                    self.assertIn(module, allowed, f"{path.relative_to(ROOT)} imports {module}")

    def test_nothing_records_audio_and_nothing_publishes(self):
        """the branch is data and prose, so the check is that no module turns anything on."""
        for path in sorted(ROOT.glob("*.py")):
            text = path.read_text().lower()
            self.assertNotIn("record(", text)
            self.assertNotIn("rtmp", text)
            self.assertNotIn("start_recording", text)

    def test_the_pages_have_no_em_dashes(self):
        for page in sorted(ROOT.rglob("*.md")):
            self.assertNotIn("\u2014", page.read_text(), f"{page.name} has an em dash")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"selftest: {result.testsRun - len(result.failures) - len(result.errors)}/{result.testsRun} pass")
    sys.exit(0 if result.wasSuccessful() else 1)
