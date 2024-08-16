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
"""Command line interface for Zephyr Scale API."""

__all__ = ["run_zapi_command_line"]

import argparse
import asyncio
import json
import os

from lsst.ts.planning.tool.zephyr_interface import ZephyrInterface


async def get_test_case(test_case_key, raw=False, **kwargs):
    """Get a test case from Zephyr Scale API."""
    zapi = setup_zephyr_interface()
    test_case = await zapi.get_test_case(test_case_key, raw=raw)
    print(json.dumps(test_case, indent=2))


def run_zapi_command_line():
    """Command line interface for Zephyr Scale API."""

    parser = argparse.ArgumentParser(description="Zephyr Scale API")
    sub_parsers = parser.add_subparsers()

    parse_get = sub_parsers.add_parser("get")
    sub_parsers_get = parse_get.add_subparsers()

    parse_test_case = sub_parsers_get.add_parser("test_case")
    parse_test_case.add_argument("test_case_key", type=str)
    parse_test_case.add_argument("--raw", action="store_true")
    parse_test_case.set_defaults(func=get_test_case)

    args = parser.parse_args()
    asyncio.run(args.func(**vars(args)))


def setup_zephyr_interface():
    """Setup Zephyr Scale API interface."""

    # Get Zephyr Scale API token
    zephyr_token = os.getenv("ZEPHYR_API_TOKEN")
    jira_token = os.getenv("JIRA_API_TOKEN")
    jira_username = os.getenv("JIRA_USERNAME")

    if zephyr_token is None:
        raise ValueError("ZEPHYR_TOKEN environment variable not set.")
    if jira_token is None:
        raise ValueError("JIRA_TOKEN environment variable not set.")
    if jira_username is None:
        raise ValueError("JIRA_USERNAME environment variable not set.")

    zapi = ZephyrInterface(
        zephyr_api_token=zephyr_token,
        jira_api_token=jira_token,
        jira_username=jira_username,
    )

    return zapi
