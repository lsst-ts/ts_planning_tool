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
"""Order the test cases of a nightly test cycle.

The functions here make no requests. A test case is represented by a dict
with a `key` (e.g. `BLOCK-T17`) and the name of its Zephyr Scale
`environment` (e.g. `1. Daytime`), which is the group it is shown under in the
Zephyr Scale UI. Groups follow the `index` of the environments.
"""

__all__ = [
    "PLACEMENT_RULES",
    "load_cycle_templates",
    "load_template_order",
    "order_template_cases",
    "place_requested_cases",
]

import os

from .utils import load_json_data

# Where each kind of requested test case goes in a nightly test cycle:
# (environment, "start" or "end" of that environment's group, anchor).
# When the anchor test case is in the cycle, the requested test cases go
# right before it instead: on-sky tests run after the initial alignment
# (BLOCK-T539) and before the survey (BLOCK-T624).
# Closed-dome night tests count as calibrations.
PLACEMENT_RULES = {
    "daytime": ("1. Daytime", "end", None),
    "on_sky": ("6. Night", "end", "BLOCK-T624"),
    "calibration": ("8. Closed Dome", "end", None),
}


def load_cycle_templates(filename="cycle_templates.json"):
    """
    Load the description of the template test cycles.

    The public API returns the test executions of a cycle in the order they
    were created, not in the order shown in the Zephyr Scale UI, so the UI
    order is kept by hand in `data/<filename>` inside this package.

    Parameters
    ----------
    filename : str, optional
        The name of the file in the package `data` folder.

    Returns
    -------
    dict
        Template test cycle key -> dict with `label`, `weekdays` (the day
        names the template is meant for) and `test_cases` (keys in UI order).
    """
    return load_json_data(filename, os.path.dirname(__file__))


def load_template_order(filename="cycle_templates.json"):
    """
    Load the saved order of the test cases in each template test cycle.

    Parameters
    ----------
    filename : str, optional
        The name of the file in the package `data` folder.

    Returns
    -------
    dict
        Template test cycle key -> list of test case keys in UI order.

    See also
    --------
    load_cycle_templates
    """
    templates = load_cycle_templates(filename)
    return {key: value["test_cases"] for key, value in templates.items()}


def _environment_index(case, env_index):
    """Return the index of the environment of `case`, or None."""
    if case.get("environment") is None:
        return None
    name = case["environment"].strip()
    if name not in env_index:
        raise ValueError(f"Unknown environment {case['environment']!r}")
    return env_index[name]


def _insertion_index(cases, environment, position, env_index):
    """
    Return where to insert new test cases so they land at the start or at
    the end of the group of `environment`, even if that group is empty.
    """
    name = environment.strip()
    if name not in env_index:
        raise ValueError(f"Unknown environment {environment!r}")
    target = env_index[name]
    indices = [_environment_index(case, env_index) for case in cases]

    if position == "end":
        before = [
            i for i, idx in enumerate(indices) if idx is not None and idx <= target
        ]
        return before[-1] + 1 if before else 0

    if position == "start":
        for i, idx in enumerate(indices):
            if idx is not None and idx >= target:
                return i
        return len(cases)

    raise ValueError(f"Position must be 'start' or 'end', got {position!r}")


def order_template_cases(order, live_cases, env_index):
    """
    Sort the test cases of a template test cycle into the saved UI order.

    Parameters
    ----------
    order : list of str
        Test case keys in UI order, from `load_template_order`.
    live_cases : list of dict
        The test cases currently in the template, each with `key` and
        `environment`, in any order.
    env_index : dict
        Environment name (stripped) -> environment index.

    Returns
    -------
    cases : list of dict
        `live_cases` in the saved order. A case missing from the saved order
        goes to the end of its environment group.
    warnings : list of str
        Differences between the saved order and the template, so whoever runs
        the tool can update the saved order.
    """
    live = {case["key"]: case for case in live_cases}
    cases = [live[key] for key in order if key in live]
    warnings = [
        f"{key} is in the saved order but no longer in the template; skipped."
        for key in order
        if key not in live
    ]

    for case in live_cases:
        if case["key"] in order:
            continue
        if case.get("environment") is None:
            cases.append(case)
            where = "the end of the cycle"
        else:
            i = _insertion_index(cases, case["environment"], "end", env_index)
            cases.insert(i, case)
            where = f"the end of {case['environment'].strip()!r}"
        warnings.append(
            f"{case['key']} is in the template but not in the saved order; "
            f"added at {where}."
        )

    return cases, warnings


def place_requested_cases(cases, requested, env_index, rules=PLACEMENT_RULES):
    """
    Add the test cases requested for a night to the template test cases.

    Parameters
    ----------
    cases : list of dict
        The ordered template test cases, each with `key` and `environment`.
    requested : list of dict
        The requested test cases in page (priority) order, each with `key`
        and `kind`, one of the keys of `rules`.
    env_index : dict
        Environment name (stripped) -> environment index.
    rules : dict, optional
        Kind -> (environment, "start" or "end", anchor test case key or
        None). If the anchor is in the cycle, the test cases of that kind go
        right before it; otherwise at the start or end of the environment's
        group.

    Returns
    -------
    cases : list of dict
        A new list with the requested test cases inserted. Requested test
        cases of one kind stay together and keep their page order, and get
        the environment of their kind.
    skipped : list of dict
        Requested test cases that were not added, with `key` and `reason`.
    """
    result = list(cases)
    present = {case["key"] for case in result}
    skipped = []
    blocks = {}

    for item in requested:
        key, kind = item["key"], item["kind"]
        if kind not in rules:
            raise ValueError(
                f"Unknown kind {kind!r} for {key}; expected one of {list(rules)}"
            )
        if key in present:
            skipped.append({"key": key, "reason": "already in the cycle"})
            continue
        present.add(key)
        blocks.setdefault(kind, []).append({"key": key, "environment": rules[kind][0]})

    for kind, block in blocks.items():
        environment, position, anchor = rules[kind]
        keys = [case["key"] for case in result]
        if anchor in keys:
            i = keys.index(anchor)
        else:
            i = _insertion_index(result, environment, position, env_index)
        result[i:i] = block

    return result, skipped
