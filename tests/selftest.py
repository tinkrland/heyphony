"""omni selftests: stdlib only. run: python3 tests/selftest.py

this branch is a contract, so most of what can go wrong is prose drifting away from `lanes.py`. the
tests here are the cheapest way to keep the page and the data saying the same thing while both are
still a promise rather than a running stack.
"""
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lanes  # noqa: E402


class TestTheLanesAreData(unittest.TestCase):
    def test_every_lane_carries_the_five_facts(self):
        for name, row in lanes.LANES.items():
            for key in ("name", "carrier", "intake", "gate", "state", "scope", "refused"):
                self.assertIn(key, row, f"{name} is missing {key}")
            self.assertEqual(row["name"], name, "a lane's name and its key disagree")
            self.assertTrue(row["gate"], f"{name} has no gate, and an ungated lane is an open route")
            self.assertIn(row["state"], lanes.STATES)

    def test_nothing_here_claims_to_be_verified(self):
        self.assertEqual(lanes.by_state("verified"), [],
                         "a lane is verified when a real message arrived, and none has")
        self.assertEqual(sorted(lanes.LANES), sorted(lanes.by_state("contract")))

    def test_the_gates_are_the_variables_the_pages_name(self):
        self.assertEqual(lanes.gates()["mail"], ["MAIL_WEBHOOK_SECRET"])
        for name, gate in lanes.gates().items():
            for variable in gate:
                self.assertEqual(variable, variable.upper(), f"{name} gate is not an env name")

    def test_the_table_is_derived_from_the_dict(self):
        rows = lanes.table_rows()
        self.assertEqual(len(rows), len(lanes.LANES))
        self.assertEqual([row[0] for row in rows], list(lanes.LANES))


class TestThePageMatchesTheData(unittest.TestCase):
    page = ROOT / "readme.md"

    def test_every_lane_is_on_the_page_with_its_state(self):
        text = self.page.read_text()
        for name, carrier, intake, gate, state in lanes.table_rows():
            self.assertIn(f"`{name}`", text, f"the page does not list {name}")
            self.assertIn(gate, text, f"the page does not name {name}'s gate")
            self.assertIn(carrier.split(",")[0], text, f"the page does not name {name}'s carrier")

    def test_the_page_admits_the_branch_is_a_contract(self):
        text = self.page.read_text()
        self.assertIn("state is `contract` on every row", text)
        self.assertIn("no catcher listens here yet", text)
        self.assertIn("seven rows, all contracts", text)

    def test_the_page_names_the_old_branch_name(self):
        text = self.page.read_text()
        self.assertIn("used to be called `comms`", text)
        self.assertIn("`omni`", text)

    def test_the_dependency_direction_is_stated_the_way_main_enforces_it(self):
        text = self.page.read_text()
        self.assertIn("`omni` imports heyphony", text)
        self.assertIn("heyphony imports nothing from `omni`", text)

    def test_the_two_inherited_rules_are_on_the_page(self):
        text = self.page.read_text()
        self.assertIn("unset means closed", text)
        self.assertIn("a room is not somebody asking", text)


class TestTheBranchStaysDecoupled(unittest.TestCase):
    def test_nothing_imports_a_carrier_sdk(self):
        allowed = {"pathlib", "sys", "unittest", "lanes"}
        for path in sorted(ROOT.rglob("*.py")):
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")):
                    module = stripped.split()[1].split(".")[0]
                    self.assertIn(module, allowed,
                                  f"{path.relative_to(ROOT)} imports {module}")

    def test_the_pages_have_no_em_dashes(self):
        for page in sorted(ROOT.rglob("*.md")):
            self.assertNotIn("\u2014", page.read_text(), f"{page.name} has an em dash")

    def test_nothing_here_carries_a_number(self):
        """the number lives on main. this branch borrows it, so it must not ship its own."""
        for path in sorted(ROOT.glob("*.py")):
            text = path.read_text().lower()
            self.assertNotIn("write_rc", text, "config writing belongs on main")
            self.assertNotIn("linphone", text)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"selftest: {result.testsRun - len(result.failures) - len(result.errors)}/{result.testsRun} pass")
    sys.exit(0 if result.wasSuccessful() else 1)
