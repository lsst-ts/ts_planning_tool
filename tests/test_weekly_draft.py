import copy
import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock

import aiohttp
from lsst.ts.planning.tool.cycle_order import load_cycle_templates
from lsst.ts.planning.tool.weekly_draft import (
    DraftWeekError,
    draft_week,
    format_report,
    validate_plan,
)
from lsst.ts.planning.tool.zephyr_interface import AddTestCasesError, ZephyrInterface

DATA = os.path.join(os.path.dirname(__file__), "data")

# Environment ids from tests/data/environments.json.
ENV_IDS = {
    "AuxTel": 6863590,
    "1. Daytime": 6824992,
    "2. Late Afternoon": 6824993,
    "3. Early Night": 6824994,
    "6. Night": 6970598,
    "7. End Night": 6831595,
}

ENVIRONMENTS = {
    "BLOCK-T17": "AuxTel",
    "BLOCK-T18": "AuxTel",
    "BLOCK-T20": "AuxTel",
    "BLOCK-T19": "AuxTel",
    "BLOCK-T594": "1. Daytime",
    "BLOCK-T244": "1. Daytime",
    "BLOCK-T529": "1. Daytime",
    "BLOCK-T250": "1. Daytime",
    "BLOCK-T145": "1. Daytime",
    "BLOCK-T144": "1. Daytime",
    "BLOCK-T51": "1. Daytime",
    "BLOCK-T3": "1. Daytime",
    "BLOCK-T4": "1. Daytime",
    "BLOCK-T70": "1. Daytime",
    "BLOCK-T239": "2. Late Afternoon",
    "BLOCK-T658": "2. Late Afternoon",
    "BLOCK-T245": "3. Early Night",
    "BLOCK-T625": "3. Early Night",
    "BLOCK-T624": "6. Night",
    "BLOCK-T539": "6. Night",
    "BLOCK-T196": "7. End Night",
    "BLOCK-T619": "7. End Night",
    "BLOCK-T242": "7. End Night",
    "BLOCK-T664": "7. End Night",
}

WEEK_DATES = [f"2026-11-{day}" for day in range(16, 23)]  # Monday to Sunday

PLAN = {
    "project": "BLOCK",
    "folder": "/LSST Survey Plans/2026/week47",
    "notes_url": "https://rubinobs.atlassian.net/wiki/spaces/LSSTOps/pages/1",
    "days": [
        {
            "date": date,
            "template": "BLOCK-R505" if i < 5 else "BLOCK-R506",
            "test_cases": [
                {"key": "BLOCK-T900", "kind": "on_sky"},
                {"key": "BLOCK-T901", "kind": "calibration"},
                {"key": "BLOCK-T624", "kind": "on_sky", "version": "1.0"},
            ]
            + ([{"key": "BLOCK-T902", "kind": "daytime"}] if i >= 5 else []),
        }
        for i, date in enumerate(WEEK_DATES)
    ],
}


def http_error(status):
    return aiohttp.ClientResponseError(MagicMock(), (), status=status, message="x")


def make_zapi(existing_cycles=(), missing_cases=(), folder=(None, "missing")):
    """A ZephyrInterface whose network methods are mocks."""
    with open(os.path.join(DATA, "environments.json")) as file:
        environments = json.load(file)["values"]
    templates = load_cycle_templates()

    zapi = MagicMock(spec=ZephyrInterface)
    zapi.get_environments = AsyncMock(return_value=environments)

    async def list_test_cases_in_cycle(key):
        # Creation order differs from the saved UI order.
        return [
            {"key": case, "version": 1, "environmentId": ENV_IDS[ENVIRONMENTS[case]]}
            for case in reversed(templates[key]["test_cases"])
        ]

    async def get(endpoint, params=None):
        key = endpoint.split("/")[1]
        if key in missing_cases:
            raise http_error(404)
        return {"key": key}

    async def get_all(endpoint, params=None):
        if endpoint == "testcycles":
            return [{"key": key, "name": name} for key, name in existing_cycles]
        if endpoint.endswith("/versions"):
            return [{"self": f"https://x/v2/{endpoint}/{n}"} for n in (1, 2)]
        raise AssertionError(endpoint)

    zapi.list_test_cases_in_cycle = AsyncMock(side_effect=list_test_cases_in_cycle)
    zapi.get = AsyncMock(side_effect=get)
    zapi.get_all = AsyncMock(side_effect=get_all)
    zapi.get_or_create_folder = AsyncMock(
        side_effect=lambda path, project, dry_run=False: (
            folder if dry_run else (123, "created")
        )
    )
    zapi.get_myself = AsyncMock(
        return_value={"accountId": "abc-123", "displayName": "Support Scientist"}
    )
    counter = iter(range(800, 900))
    zapi.create_test_cycle = AsyncMock(
        side_effect=lambda *args, **kwargs: {"key": f"BLOCK-R{next(counter)}"}
    )
    zapi.add_test_cases_to_cycle = AsyncMock(
        side_effect=lambda key, cases: [
            {"key": case["key"], "environment": case["environment"], "id": 1}
            for case in cases
        ]
    )
    return zapi


def keys(day):
    return [case["key"] for case in day["test_cases"]]


class TestWeeklyDraft(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.templates = load_cycle_templates()

    def test_validate_plan(self):
        self.assertListEqual(validate_plan(PLAN, self.templates), [])

        plan = copy.deepcopy(PLAN)
        plan["folder"] = "week47"
        plan["days"][1]["date"] = plan["days"][0]["date"]
        plan["days"][2]["template"] = "BLOCK-R1"
        plan["days"][3]["test_cases"][0] = {"key": "BLOCK:T757", "kind": "nightly"}
        problems = validate_plan(plan, self.templates)
        self.assertEqual(len(problems), 5)

    async def test_dry_run(self):
        zapi = make_zapi()

        report = await draft_week(zapi, PLAN)

        self.assertTrue(report["dry_run"])
        zapi.create_test_cycle.assert_not_called()
        zapi.add_test_cases_to_cycle.assert_not_called()
        for call in zapi.get_or_create_folder.call_args_list:
            self.assertTrue(call.kwargs["dry_run"])
        self.assertEqual(len(report["days"]), 7)
        self.assertEqual(report["folder"]["status"], "missing")

        monday = report["days"][0]
        self.assertEqual(monday["name"], "2026-11-16 LSST Survey Plan")
        self.assertEqual(monday["planned_start"], "2026-11-16T03:00:00Z")
        self.assertEqual(monday["planned_end"], "2026-11-17T03:00:00Z")
        template = self.templates["BLOCK-R505"]["test_cases"]
        # Template cases keep the saved UI order, not the API order.
        self.assertListEqual([k for k in keys(monday) if k in template], template)
        # On-sky at the start of 6. Night, calibration at the end.
        result = keys(monday)
        self.assertEqual(result[result.index("BLOCK-T900") + 1], "BLOCK-T624")
        self.assertEqual(result[-1], "BLOCK-T901")
        self.assertEqual(monday["test_cases"][-1]["environment"], "8. Closed Dome")
        self.assertEqual(monday["test_cases"][-1]["source"], "calibration")
        # T624 is in the template, so it is skipped, not added twice.
        self.assertListEqual(
            monday["skipped"], [{"key": "BLOCK-T624", "reason": "already in the cycle"}]
        )
        self.assertNotIn("BLOCK-T902", result)

        saturday = report["days"][5]
        self.assertEqual(saturday["template"], "BLOCK-R506")
        result = keys(saturday)
        self.assertEqual(result[result.index("BLOCK-T51") + 1], "BLOCK-T902")

        self.assertEqual(
            report["description"],
            '<a href="https://rubinobs.atlassian.net/wiki/spaces/LSSTOps/pages/1">'
            "2026 W47 Test Cycle Publication Notes</a>",
        )
        self.assertEqual(report["owner"]["accountId"], "abc-123")
        # The plan asks for T624 1.0 and the latest is 2.0.
        self.assertTrue(any("BLOCK-T624" in w for w in report["warnings"]))
        self.assertIn("2026-11-16 LSST Survey Plan", format_report(report))

    async def test_execute(self):
        zapi = make_zapi()

        report = await draft_week(zapi, PLAN, dry_run=False)

        self.assertEqual(
            report["folder"], {"path": PLAN["folder"], "id": 123, "status": "created"}
        )
        self.assertEqual(zapi.create_test_cycle.call_count, 7)
        first = zapi.create_test_cycle.call_args_list[0]
        self.assertEqual(first.args[0], "2026-11-16 LSST Survey Plan")
        self.assertEqual(first.kwargs["folder_id"], 123)
        self.assertEqual(first.kwargs["owner_id"], "abc-123")
        self.assertEqual(first.kwargs["status_name"], "Not Executed")
        self.assertEqual(first.kwargs["planned_start_date"], "2026-11-16T03:00:00Z")
        self.assertEqual(first.kwargs["description"], report["description"])

        added = zapi.add_test_cases_to_cycle.call_args_list[0]
        self.assertEqual(added.args[0], "BLOCK-R800")
        self.assertListEqual(
            [case["key"] for case in added.args[1]], keys(report["days"][0])
        )
        self.assertListEqual(
            [day["cycle_key"] for day in report["days"]],
            [f"BLOCK-R{n}" for n in range(800, 807)],
        )
        for day in report["days"]:
            self.assertEqual(day["added"], len(day["test_cases"]))

    async def test_refuses_existing_cycles(self):
        zapi = make_zapi(
            existing_cycles=[("BLOCK-R777", "2026-11-18 LSST Survey Plan ")],
            folder=(456, "found"),
        )

        with self.assertRaises(ValueError) as context:
            await draft_week(zapi, PLAN, dry_run=False)

        self.assertIn("BLOCK-R777", str(context.exception))
        zapi.create_test_cycle.assert_not_called()
        zapi.add_test_cases_to_cycle.assert_not_called()

    async def test_refuses_missing_test_case(self):
        zapi = make_zapi(missing_cases=["BLOCK-T901"])

        with self.assertRaises(ValueError) as context:
            await draft_week(zapi, PLAN, dry_run=False)

        self.assertIn("BLOCK-T901", str(context.exception))
        zapi.create_test_cycle.assert_not_called()

    async def test_invalid_plan_makes_no_request(self):
        zapi = make_zapi()
        plan = copy.deepcopy(PLAN)
        plan["days"] = []

        with self.assertRaises(ValueError):
            await draft_week(zapi, plan)

        zapi.get_environments.assert_not_called()

    async def test_stops_on_write_error(self):
        zapi = make_zapi()
        calls = {"n": 0}

        async def add(key, cases):
            calls["n"] += 1
            if calls["n"] == 2:
                error = AddTestCasesError(key, cases[3]["key"], [{"key": "x"}] * 3)
                error.__cause__ = http_error(400)
                raise error
            return [{"key": case["key"], "id": 1} for case in cases]

        zapi.add_test_cases_to_cycle = AsyncMock(side_effect=add)

        with self.assertRaises(DraftWeekError) as context:
            await draft_week(zapi, PLAN, dry_run=False)

        days = context.exception.report["days"]
        self.assertEqual(days[0]["cycle_key"], "BLOCK-R800")
        self.assertEqual(days[1]["cycle_key"], "BLOCK-R801")
        self.assertEqual(days[1]["added"], 3)
        self.assertIsNone(days[2]["cycle_key"])
        self.assertEqual(zapi.create_test_cycle.call_count, 2)
        self.assertIn("ONLY 3 ADDED", format_report(context.exception.report))

    async def test_exclude(self):
        zapi = make_zapi()
        plan = copy.deepcopy(PLAN)
        plan["days"][5]["exclude"] = ["BLOCK-T625", "BLOCK-T539", "BLOCK-T999"]

        report = await draft_week(zapi, plan)

        saturday = report["days"][5]
        self.assertNotIn("BLOCK-T625", keys(saturday))
        self.assertNotIn("BLOCK-T539", keys(saturday))
        self.assertListEqual(saturday["excluded"], ["BLOCK-T625", "BLOCK-T539"])
        self.assertEqual(len(saturday["test_cases"]), 24 - 2 + 3)
        # Other nights keep them.
        self.assertIn("BLOCK-T625", keys(report["days"][6]))
        self.assertListEqual(report["days"][6]["excluded"], [])
        # On-sky still goes before the first 6. Night case left (T624).
        result = keys(saturday)
        self.assertEqual(result[result.index("BLOCK-T900") + 1], "BLOCK-T624")
        self.assertTrue(any("BLOCK-T999" in w for w in report["warnings"]))
        self.assertIn("excluded from the template", format_report(report))

    def test_validate_plan_exclude(self):
        plan = copy.deepcopy(PLAN)
        plan["days"][0]["exclude"] = ["BLOCK-T900", "T625"]
        plan["days"][1]["exclude"] = "BLOCK-T625"

        problems = validate_plan(plan, self.templates)

        self.assertEqual(len(problems), 3)
        self.assertTrue(any("both requested and excluded" in p for p in problems))

    async def test_weekday_template_warning(self):
        zapi = make_zapi()
        plan = copy.deepcopy(PLAN)
        plan["days"][5]["template"] = "BLOCK-R505"  # a Saturday

        report = await draft_week(zapi, plan)

        self.assertTrue(any("Saturday" in w for w in report["warnings"]))


if __name__ == "__main__":
    unittest.main()
