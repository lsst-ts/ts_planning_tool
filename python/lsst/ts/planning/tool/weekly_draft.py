# This file is part of ts_planning_tool.
#
# Developed for the LSST Data Management System.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Draft the nightly test cycles of a week from a JSON plan.

A plan looks like::

    {
      "project": "BLOCK",
      "folder": "/LSST Survey Plans/2026/week47",
      "notes_url": "https://rubinobs.atlassian.net/wiki/...",
      "days": [
        {"date": "2026-11-16", "template": "BLOCK-R505",
         "test_cases": [{"key": "BLOCK-T724", "kind": "on_sky"},
                        {"key": "BLOCK-T624", "kind": "on_sky",
                         "version": "2.0"}],
         "exclude": ["BLOCK-T625", "BLOCK-T539"]}
      ]
    }

Each nightly cycle gets the template's test cases, in the saved UI order,
minus the ones in `exclude` (optional), plus the requested ones, placed by
`kind` (see `PLACEMENT_RULES`).
"""

__all__ = [
    "CYCLE_NAME",
    "DraftWeekError",
    "draft_week",
    "format_report",
    "validate_plan",
]

import re
from datetime import date, timedelta

import aiohttp

from .cycle_order import (
    PLACEMENT_RULES,
    load_cycle_templates,
    order_template_cases,
    place_requested_cases,
)
from .zephyr_interface import AddTestCasesError

CYCLE_NAME = "{date} LSST Survey Plan"
CYCLE_STATUS = "Not Executed"
# Nights run from midnight to midnight at UTC-3, as in the cycles drafted by
# hand (fixed on purpose, without daylight-saving changes).
NIGHT_START_UTC = "T03:00:00Z"


class DraftWeekError(RuntimeError):
    """
    Raised when `draft_week` stops after it started writing.

    Attributes
    ----------
    report : dict
        The report up to the error. Days with a `cycle_key` were created;
        `added` tells how many of their test cases were added.
    """

    def __init__(self, message, report):
        super().__init__(message)
        self.report = report


def _parse_version(value):
    """Return the major version of `2`, `"2"` or `"2.0"` as an int."""
    return int(str(value).strip().split(".")[0])


def validate_plan(plan, templates):
    """
    Check a plan before any request is made.

    Parameters
    ----------
    plan : dict
        The plan, as described in the module docstring.
    templates : dict
        The template test cycles, from `load_cycle_templates`.

    Returns
    -------
    list of str
        The problems found; empty if the plan is valid.
    """
    problems = []
    project = plan.get("project", "BLOCK")

    if not str(plan.get("folder", "")).startswith("/"):
        problems.append(
            "`folder` must be a path such as /LSST Survey Plans/2026/week47"
        )
    if not re.match(r"https?://", str(plan.get("notes_url", ""))):
        problems.append("`notes_url` must be the URL of the Confluence page")

    days = plan.get("days")
    if not isinstance(days, list) or not days:
        return problems + ["`days` must be a non-empty list"]

    seen_dates = set()
    for i, day in enumerate(days):
        where = f"days[{i}]"
        try:
            date.fromisoformat(day.get("date", ""))
        except (TypeError, ValueError):
            problems.append(f"{where}: `date` must look like 2026-11-16")
        if day.get("date") in seen_dates:
            problems.append(f"{where}: date {day.get('date')} appears twice")
        seen_dates.add(day.get("date"))

        if day.get("template") not in templates:
            problems.append(
                f"{where}: unknown template {day.get('template')!r}; "
                f"expected one of {list(templates)}"
            )

        for j, item in enumerate(day.get("test_cases", [])):
            if not re.fullmatch(rf"{project}-T[0-9]+", str(item.get("key", ""))):
                problems.append(f"{where}.test_cases[{j}]: bad key {item.get('key')!r}")
            if item.get("kind") not in PLACEMENT_RULES:
                problems.append(
                    f"{where}.test_cases[{j}]: kind must be one of "
                    f"{list(PLACEMENT_RULES)}, got {item.get('kind')!r}"
                )
            if item.get("version") is not None:
                try:
                    _parse_version(item["version"])
                except ValueError:
                    problems.append(
                        f"{where}.test_cases[{j}]: bad version {item['version']!r}"
                    )

        exclude = day.get("exclude", [])
        if not isinstance(exclude, list):
            problems.append(f"{where}: `exclude` must be a list of test case keys")
            continue
        requested = {item.get("key") for item in day.get("test_cases", [])}
        for key in exclude:
            if not re.fullmatch(rf"{project}-T[0-9]+", str(key)):
                problems.append(f"{where}.exclude: bad key {key!r}")
            elif key in requested:
                problems.append(f"{where}: {key} is both requested and excluded")

    return problems


async def _latest_version(zapi, test_case_key):
    """Return the latest version number of a test case."""
    versions = await zapi.get_all(f"testcases/{test_case_key}/versions")
    numbers = [
        int(match.group(1))
        for version in versions
        if (match := re.search(r"/versions/([0-9]+)", version.get("self", "")))
    ]
    return max(numbers, default=1)


async def draft_week(zapi, plan, dry_run=True, templates=None):
    """
    Draft the test cycles of a week.

    Every check is done before the first write: the plan, the templates,
    that the requested test cases exist, and that no cycle with the same name
    is already in the week folder. A dry run makes GET requests only.

    Parameters
    ----------
    zapi : ZephyrInterface
        The interface to use; needs Jira credentials for the owner.
    plan : dict
        The plan, as described in the module docstring. `owner_account_id`
        is optional; by default the owner is the person running the tool.
    dry_run : bool, optional
        If True (default), only report what would be created.
    templates : dict, optional
        The template test cycles; by default `load_cycle_templates()`.

    Returns
    -------
    dict
        The report: `dry_run`, `folder`, `owner`, `description`, `warnings`
        and `days`, one per plan day with its `name`, `template`, planned
        dates, ordered `test_cases` (each with `key`, `environment` and
        `source`, the kind or "template"), `skipped`, `excluded` (template
        test cases left out) and, when written, `cycle_key` and `added`.

    Raises
    ------
    ValueError
        If a check fails. Nothing was written.
    DraftWeekError
        If a write fails. Its `report` tells what was created.
    """
    templates = templates if templates is not None else load_cycle_templates()
    problems = validate_plan(plan, templates)
    if problems:
        raise ValueError("Invalid plan:\n- " + "\n- ".join(problems))

    project = plan.get("project", "BLOCK")
    days = sorted(plan["days"], key=lambda day: day["date"])
    first = date.fromisoformat(days[0]["date"]).isocalendar()
    title = plan.get(
        "notes_title",
        f"{first.year} W{first.week:02d} Test Cycle Publication Notes",
    )
    report = {
        "dry_run": dry_run,
        "folder": {"path": plan["folder"]},
        "description": f'<a href="{plan["notes_url"]}">{title}</a>',
        "warnings": [],
        "days": [],
    }

    # Environments: names for the template executions, indices for ordering.
    environments = await zapi.get_environments(project)
    env_name = {env["id"]: env["name"].strip() for env in environments}
    env_index = {env["name"].strip(): env["index"] for env in environments}

    # Templates, in their saved UI order.
    ordered_templates = {}
    for key in dict.fromkeys(day["template"] for day in days):
        live = [
            {"key": case["key"], "environment": env_name.get(case["environmentId"])}
            for case in await zapi.list_test_cases_in_cycle(key)
        ]
        cases, warnings = order_template_cases(
            templates[key]["test_cases"], live, env_index
        )
        ordered_templates[key] = cases
        report["warnings"] += [f"{key}: {warning}" for warning in warnings]

    # Requested test cases must exist; requested versions are only reported,
    # because the API always uses the latest version.
    requested = {}
    for day in days:
        for item in day.get("test_cases", []):
            versions = requested.setdefault(item["key"], set())
            if item.get("version") is not None:
                versions.add(_parse_version(item["version"]))

    missing = []
    for key, versions in requested.items():
        try:
            await zapi.get(f"testcases/{key}")
        except aiohttp.ClientResponseError as error:
            if error.status == 404:
                missing.append(key)
                continue
            raise
        if versions:
            latest = await _latest_version(zapi, key)
            for version in sorted(versions - {latest}):
                report["warnings"].append(
                    f"{key}: the plan asks for version {version}.0, but the "
                    f"execution will use the latest version, {latest}.0 (the "
                    f"API cannot choose a version)."
                )
    if missing:
        raise ValueError(f"These test cases do not exist: {', '.join(missing)}")

    # Week folder, and refuse to create cycles that already exist in it.
    folder_id, folder_status = await zapi.get_or_create_folder(
        plan["folder"], project, dry_run=True
    )
    report["folder"].update(id=folder_id, status=folder_status)
    names = {CYCLE_NAME.format(date=day["date"]) for day in days}
    if folder_id is not None:
        existing = await zapi.get_all(
            "testcycles", {"projectKey": project, "folderId": folder_id}
        )
        duplicates = sorted(
            f"{cycle['key']} {cycle['name'].strip()!r}"
            for cycle in existing
            if cycle["name"].strip() in names
        )
        if duplicates:
            raise ValueError(
                f"These test cycles already exist in {plan['folder']}: "
                f"{', '.join(duplicates)}. Nothing was created."
            )

    # Owner: the person running the tool, unless the plan says otherwise.
    if plan.get("owner_account_id"):
        report["owner"] = {"accountId": plan["owner_account_id"]}
    else:
        myself = await zapi.get_myself()
        report["owner"] = {
            "accountId": myself["accountId"],
            "displayName": myself.get("displayName"),
        }

    # Cycle contents.
    for day in days:
        night = date.fromisoformat(day["date"])
        weekday = night.strftime("%A")
        allowed = templates[day["template"]].get("weekdays")
        if allowed and weekday not in allowed:
            report["warnings"].append(
                f"{day['date']} is a {weekday}, but {day['template']} is the "
                f"template for {', '.join(allowed)}."
            )

        all_template_keys = {case["key"] for case in ordered_templates[day["template"]]}
        exclude = day.get("exclude", [])
        excluded = [key for key in exclude if key in all_template_keys]
        for key in exclude:
            if key not in all_template_keys:
                report["warnings"].append(
                    f"{day['date']}: {key} is not in {day['template']}; "
                    f"nothing to exclude."
                )
        template_cases = [
            case
            for case in ordered_templates[day["template"]]
            if case["key"] not in excluded
        ]
        template_keys = {case["key"] for case in template_cases}
        kinds = {item["key"]: item["kind"] for item in day.get("test_cases", [])}
        cases, skipped = place_requested_cases(
            template_cases, day.get("test_cases", []), env_index
        )
        report["days"].append(
            {
                "date": day["date"],
                "name": CYCLE_NAME.format(date=day["date"]),
                "template": day["template"],
                "planned_start": f"{night.isoformat()}{NIGHT_START_UTC}",
                "planned_end": f"{(night + timedelta(days=1)).isoformat()}"
                f"{NIGHT_START_UTC}",
                "test_cases": [
                    {
                        "key": case["key"],
                        "environment": case["environment"],
                        "source": (
                            "template"
                            if case["key"] in template_keys
                            else kinds[case["key"]]
                        ),
                    }
                    for case in cases
                ],
                "skipped": skipped,
                "excluded": excluded,
                "cycle_key": None,
            }
        )

    if dry_run:
        return report

    # Writes. Nothing above wrote anything.
    if folder_id is None:
        folder_id, folder_status = await zapi.get_or_create_folder(
            plan["folder"], project
        )
        report["folder"].update(id=folder_id, status=folder_status)

    for day_report in report["days"]:
        try:
            cycle = await zapi.create_test_cycle(
                day_report["name"],
                project_key=project,
                description=report["description"],
                planned_start_date=day_report["planned_start"],
                planned_end_date=day_report["planned_end"],
                folder_id=folder_id,
                status_name=CYCLE_STATUS,
                owner_id=report["owner"]["accountId"],
            )
        except aiohttp.ClientResponseError as error:
            raise DraftWeekError(
                f"Could not create {day_report['name']!r}: {error.message}", report
            ) from error
        day_report["cycle_key"] = cycle["key"]

        try:
            added = await zapi.add_test_cases_to_cycle(
                cycle["key"], day_report["test_cases"]
            )
        except AddTestCasesError as error:
            day_report["added"] = len(error.added)
            raise DraftWeekError(
                f"{error} ({error.__cause__.message})", report
            ) from error
        day_report["added"] = len(added)

    return report


def format_report(report):
    """
    Format a `draft_week` report for people.

    Parameters
    ----------
    report : dict
        The report returned by `draft_week` (or `DraftWeekError.report`).

    Returns
    -------
    str
        The report as text.
    """
    lines = []
    if report["dry_run"]:
        lines += [
            "DRY RUN: nothing was written. Add --execute to create the cycles.",
            "",
        ]

    folder = report["folder"]
    folder_state = {
        "found": f"exists, id {folder.get('id')}",
        "created": f"created, id {folder.get('id')}",
        "missing": "will be created",
    }.get(folder.get("status"), "not checked")
    lines.append(f"Folder:      {folder['path']} ({folder_state})")
    owner = report.get("owner", {})
    lines.append(f"Owner:       {owner.get('displayName') or owner.get('accountId')}")
    lines.append(f"Description: {report['description']}")

    for day in report["days"]:
        requested = sum(case["source"] != "template" for case in day["test_cases"])
        cycle = f" -> {day['cycle_key']}" if day.get("cycle_key") else ""
        lines += [
            "",
            f"{day['name']} ({day['template']}{cycle}): "
            f"{len(day['test_cases'])} test cases, {requested} requested",
        ]
        if "added" in day and day["added"] != len(day["test_cases"]):
            lines.append(f"  ONLY {day['added']} ADDED BEFORE THE ERROR")
        for i, case in enumerate(day["test_cases"], start=1):
            mark = "+" if case["source"] != "template" else " "
            kind = f"  ({case['source']})" if case["source"] != "template" else ""
            lines.append(
                f"  {mark}{i:3d}. {case['key']:<12} {case['environment'] or '-'}{kind}"
            )
        for item in day["skipped"]:
            lines.append(f"  skipped {item['key']}: {item['reason']}")
        if day.get("excluded"):
            lines.append(f"  excluded from the template: {', '.join(day['excluded'])}")

    if report["warnings"]:
        lines += ["", "Warnings:"]
        lines += [f"  - {warning}" for warning in report["warnings"]]

    return "\n".join(lines)
