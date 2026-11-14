#!/usr/bin/env python
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
"""Link the new test cycles from a "Test Cycle Publication notes" page.

Fills each night's empty "Test Cycle:" line with a link to its cycle and
links "Test Cycles for this week" to the week folder, as on the W46 page.

    zapi draft week plan.json --execute --json > report.json
    python link_cycles.py <page id or URL> report.json            # preview
    python link_cycles.py <page id or URL> report.json --execute  # save

It refuses to run unless it finds exactly one empty "Test Cycle:" line per
night of the report, and saves with a version check (fails if someone saved
the page in between). Confluence keeps the previous version in the history.
"""

import argparse
import json
import re
import sys

from confluence_page import SITE, page_id, request

ZEPHYR = (
    SITE + "/projects/BLOCK?selectedItem=com.atlassian.plugins.atlassian-connect-"
    "plugin:com.kanoah.test-manager__main-project-page#!/v2/"
)


def link_cycles(storage, report):
    """Return the new storage and a list of the changes."""
    folder_id = report["folder"]["id"]
    cycles = {day["date"]: day["cycle_key"] for day in report["days"]}
    changes = []

    pattern = re.compile(r'(<p local-id="[^"]+">Test Cycle:\s*)(</p>)')
    matches = list(pattern.finditer(storage))
    if len(matches) != len(cycles):
        raise ValueError(
            f"Expected {len(cycles)} empty 'Test Cycle:' lines, found "
            f"{len(matches)}; fill them by hand."
        )
    parts, last = [], 0
    for match in matches:
        dates = re.findall(
            r'<time datetime="(\d{4}-\d{2}-\d{2})"', storage[: match.start()]
        )
        night = dates[-1] if dates else None
        if night not in cycles:
            raise ValueError(f"A 'Test Cycle:' line is under {night}, not a night.")
        key = cycles.pop(night)
        href = f"{ZEPHYR}testCycle/{key}?folderId={folder_id}&amp;projectId=10064"
        parts += [
            storage[last : match.start()],
            match.group(1),
            f'<a href="{href}">{key}</a>',
            match.group(2),
        ]
        last = match.end()
        changes.append(f"{night}: Test Cycle: {key}")
    parts.append(storage[last:])
    storage = "".join(parts)

    top = re.compile(r'(<p local-id="[^"]+">)(Test Cycles for this week)(</p>)')
    if len(top.findall(storage)) == 1:
        href = f"{ZEPHYR}testCycles?folderId={folder_id}&amp;projectId=10064"
        storage = top.sub(
            lambda m: f'{m.group(1)}<a href="{href}">{m.group(2)}</a>{m.group(3)}',
            storage,
        )
        changes.append(f"Test Cycles for this week -> folder {folder_id}")

    return storage, changes


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("page", help="Page id or URL")
    parser.add_argument("report", help="JSON report of zapi draft week --execute")
    parser.add_argument("--execute", action="store_true", help="Save the page")
    args = parser.parse_args()

    with open(args.report) as file:
        report = json.load(file)
    if any(not day.get("cycle_key") for day in report["days"]):
        sys.exit("The report has nights without a cycle key; run --execute first.")

    page = request(f"content/{page_id(args.page)}?expand=body.storage,version")
    try:
        storage, changes = link_cycles(page["body"]["storage"]["value"], report)
    except ValueError as error:
        sys.exit(f"ERROR: {error}")
    print("\n".join(changes))
    if not args.execute:
        print("Preview only; add --execute to save the page.")
        return

    body = {
        "id": page["id"],
        "type": "page",
        "title": page["title"],
        "version": {
            "number": page["version"]["number"] + 1,
            "message": "Link the test cycles (drafted with ts_planning_tool)",
        },
        "body": {"storage": {"value": storage, "representation": "storage"}},
    }
    result = request(f"content/{page['id']}", method="PUT", payload=body)
    print(f"Saved version {result['version']['number']} of {page['title']!r}")


if __name__ == "__main__":
    sys.exit(main())
