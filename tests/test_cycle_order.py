import json
import os
import unittest

from lsst.ts.planning.tool.cycle_order import (
    PLACEMENT_RULES,
    load_cycle_templates,
    load_template_order,
    order_template_cases,
    place_requested_cases,
    template_entries,
)


def load_env_index():
    filepath = os.path.join(os.path.dirname(__file__), "data", "environments.json")
    with open(filepath, "r") as file:
        environments = json.load(file)["values"]
    return {env["name"].strip(): env["index"] for env in environments}


def keys(cases):
    return [case["key"] for case in cases]


class TestCycleOrder(unittest.TestCase):
    def setUp(self):
        self.env_index = load_env_index()
        self.order = load_template_order()
        self.templates = load_cycle_templates()
        self.r505 = template_entries(self.templates["BLOCK-R505"])

    def test_load_template_order(self):
        self.assertSetEqual(set(self.order), {"BLOCK-R505", "BLOCK-R506"})
        self.assertEqual(len(self.order["BLOCK-R505"]), 22)
        self.assertEqual(len(self.order["BLOCK-R506"]), 25)
        for cases in self.order.values():
            self.assertEqual(len(cases), len(set(cases)))

    def test_placement_environments_exist(self):
        for environment, _, _ in PLACEMENT_RULES.values():
            self.assertIn(environment, self.env_index)

    def test_saved_order_is_grouped_by_environment(self):
        for key, template in self.templates.items():
            entries = template_entries(template)
            self.assertTrue(all(entry["environment"] for entry in entries), key)
            indices = [self.env_index[entry["environment"]] for entry in entries]
            self.assertListEqual(indices, sorted(indices), key)

    def test_order_template_cases(self):
        live = list(reversed(self.r505))

        cases, warnings = order_template_cases(
            self.order["BLOCK-R505"], live, self.env_index
        )

        self.assertListEqual(keys(cases), self.order["BLOCK-R505"])
        self.assertListEqual(warnings, [])

    def test_order_template_cases_with_differences(self):
        live = [case for case in self.r505 if case["key"] != "BLOCK-T51"]
        live.insert(0, {"key": "BLOCK-T999", "environment": "2. Late Afternoon "})

        cases, warnings = order_template_cases(
            self.order["BLOCK-R505"], live, self.env_index
        )

        self.assertNotIn("BLOCK-T51", keys(cases))
        # New case goes to the end of its group, before 3. Early Night.
        i = keys(cases).index("BLOCK-T999")
        self.assertEqual(keys(cases)[i - 1], "BLOCK-T245")
        self.assertEqual(keys(cases)[i + 1], "BLOCK-T625")
        self.assertEqual(len(warnings), 2)

    def test_place_requested_cases(self):
        requested = [
            {"key": "BLOCK-T800", "kind": "calibration"},
            {"key": "BLOCK-T700", "kind": "on_sky"},
            {"key": "BLOCK-T600", "kind": "daytime"},
            {"key": "BLOCK-T701", "kind": "on_sky"},
            {"key": "BLOCK-T70", "kind": "daytime"},
            {"key": "BLOCK-T700", "kind": "calibration"},
            {"key": "BLOCK-T801", "kind": "calibration"},
        ]

        cases, skipped = place_requested_cases(self.r505, requested, self.env_index)
        result = keys(cases)

        # Daytime: right before T250 (TMA unpark, last of the day).
        i = result.index("BLOCK-T600")
        self.assertListEqual(
            result[i - 1 : i + 2], ["BLOCK-T70", "BLOCK-T600", "BLOCK-T250"]
        )
        # On-sky: after the alignment (T539), right before the survey (T624),
        # in page order.
        i = result.index("BLOCK-T700")
        self.assertListEqual(
            result[i - 1 : i + 3],
            ["BLOCK-T539", "BLOCK-T700", "BLOCK-T701", "BLOCK-T624"],
        )
        # Calibration: end of the cycle, in page order.
        self.assertListEqual(result[-2:], ["BLOCK-T800", "BLOCK-T801"])
        self.assertEqual(cases[-1]["environment"], "8. Closed Dome")
        # Template cases keep their order.
        self.assertListEqual(
            [key for key in result if key in self.order["BLOCK-R505"]],
            self.order["BLOCK-R505"],
        )
        self.assertListEqual(
            skipped,
            [
                {"key": "BLOCK-T70", "reason": "already in the cycle"},
                {"key": "BLOCK-T700", "reason": "already in the cycle"},
            ],
        )
        self.assertEqual(len(self.r505), 22)  # input not modified

    def test_place_late_afternoon(self):
        cases, _ = place_requested_cases(
            self.r505,
            [
                {"key": "BLOCK-T751", "kind": "late_afternoon"},
                {"key": "BLOCK-T752", "kind": "late_afternoon"},
            ],
            self.env_index,
        )

        result = keys(cases)
        i = result.index("BLOCK-T751")
        self.assertListEqual(
            result[i - 1 : i + 3],
            ["BLOCK-T250", "BLOCK-T751", "BLOCK-T752", "BLOCK-T239"],
        )
        self.assertEqual(cases[i]["environment"], "2. Late Afternoon")

    def test_place_daytime_without_tma_unpark(self):
        # No T250 (anchor): daytime goes to the end of 1. Daytime.
        template = [case for case in self.r505 if case["key"] != "BLOCK-T250"]

        cases, _ = place_requested_cases(
            template, [{"key": "BLOCK-T600", "kind": "daytime"}], self.env_index
        )

        result = keys(cases)
        i = result.index("BLOCK-T600")
        self.assertEqual(result[i - 1], "BLOCK-T70")
        self.assertEqual(result[i + 1], "BLOCK-T239")

    def test_place_on_sky_without_survey(self):
        # No T624 (anchor): on-sky goes to the end of 6. Night.
        template = [case for case in self.r505 if case["key"] != "BLOCK-T624"]

        cases, _ = place_requested_cases(
            template, [{"key": "BLOCK-T700", "kind": "on_sky"}], self.env_index
        )

        result = keys(cases)
        i = result.index("BLOCK-T700")
        self.assertEqual(result[i - 1], "BLOCK-T539")
        self.assertEqual(result[i + 1], "BLOCK-T664")

    def test_place_on_sky_without_night_group(self):
        template = [case for case in self.r505 if case["environment"] != "6. Night"]

        cases, _ = place_requested_cases(
            template, [{"key": "BLOCK-T700", "kind": "on_sky"}], self.env_index
        )

        result = keys(cases)
        i = result.index("BLOCK-T700")
        self.assertEqual(result[i - 1], "BLOCK-T625")
        self.assertEqual(result[i + 1], "BLOCK-T664")

    def test_place_unknown_kind(self):
        with self.assertRaises(ValueError):
            place_requested_cases(
                self.r505, [{"key": "BLOCK-T1", "kind": "other"}], self.env_index
            )


if __name__ == "__main__":
    unittest.main()
