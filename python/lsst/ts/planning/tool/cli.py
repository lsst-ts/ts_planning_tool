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
import logging
import os

from lsst.ts.planning.tool.zephyr_interface import ZephyrInterface


async def get_test_execution(test_execution_key, parse="raw", indent=4, **kwargs):
    """Get a test execution from Zephyr Scale API."""
    zapi = setup_zephyr_interface()
    test_execution = await zapi.get_test_execution(test_execution_key, parse=parse)
    print(json.dumps(test_execution, indent=indent))


async def get_test_case(test_case_key, parse="raw", indent=4, **kwargs):
    """Get a test case from Zephyr Scale API."""
    zapi = setup_zephyr_interface()
    test_case = await zapi.get_test_case(test_case_key, parse=parse)
    print(json.dumps(test_case, indent=indent))


async def get_test_cycle(test_cycle_key, parse="raw", indent=4, **kwargs):
    """Get a test cycle from Zephyr Scale API."""
    zapi = setup_zephyr_interface()
    test_cycle = await zapi.get_test_cycle(test_cycle_key, parse=parse)
    print(json.dumps(test_cycle, indent=indent))


async def get_steps_in_test_case(test_case_key, indent=4, **kwargs):
    """Get steps in a test case from Zephyr Scale API."""
    zapi = setup_zephyr_interface()
    test_steps = await zapi.get_steps_in_test_case(test_case_key)
    print(json.dumps(test_steps, indent=indent))


async def get_user(user_id, indent=4, **kwargs):
    """Get the user name based on its Jira ID number."""
    zapi = setup_zephyr_interface()
    user_name = await zapi.get_user_name(user_id)
    print(json.dumps(user_name, indent=indent))


async def list_test_executions(
    key, indent=4, max_results=5, only_last=False, parse="raw", **kwargs
):
    """List test executions for a test cycle or a test case from Zephyr Scale
    API."""
    zapi = setup_zephyr_interface()
    test_executions = await zapi.list_test_executions(
        key, max_results=max_results, only_last=only_last, parse=parse
    )
    print(json.dumps(test_executions, indent=indent))


def run_zapi_command_line():
    """Command line interface for Zephyr Scale API."""

    parser = argparse.ArgumentParser(description="Zephyr Scale API")
    sub_parsers = parser.add_subparsers()
    sub_parsers.required = True

    parse_get = sub_parsers.add_parser(
        "get",
        help="Get a single instance of Test Case, Test Cycle, or Test Execution from Zephyr Scale API",
    )
    sub_parsers_get = parse_get.add_subparsers()
    sub_parsers_get.required = True

    parse_test_case = sub_parsers_get.add_parser("test_case")
    parse_test_case.set_defaults(func=get_test_case)
    parse_test_case.add_argument("test_case_key", type=str)
    parse_test_case.add_argument("-i", "--indent", type=int, default=4)
    parse_test_case.add_argument(
        "-p", "--parse", choices=["raw", "full", "simple"], default="raw"
    )

    parse_test_cycle = sub_parsers_get.add_parser("test_cycle")
    parse_test_cycle.set_defaults(func=get_test_cycle)
    parse_test_cycle.add_argument("test_cycle_key", type=str)
    parse_test_cycle.add_argument("--indent", type=int, default=4)
    parse_test_cycle.add_argument(
        "-p", "--parse", choices=["raw", "full", "simple"], default="raw"
    )

    parse_test_execution = sub_parsers_get.add_parser("test_execution")
    parse_test_execution.set_defaults(func=get_test_execution)
    parse_test_execution.add_argument("test_execution_key", type=str)
    parse_test_execution.add_argument("-i", "--indent", type=int, default=4)
    parse_test_execution.add_argument(
        "-p", "--parse", choices=["raw", "full", "simple"], default="raw"
    )

    parse_test_steps = sub_parsers_get.add_parser("steps")
    parse_test_steps.set_defaults(func=get_steps_in_test_case)
    parse_test_steps.add_argument("test_case_key", type=str)
    parse_test_steps.add_argument("-i", "--indent", type=int, default=4)

    parse_test_steps = sub_parsers_get.add_parser("user")
    parse_test_steps.set_defaults(func=get_user)
    parse_test_steps.add_argument("user_id", type=str)
    parse_test_steps.add_argument("--indent", type=int, default=4)

    parse_list = sub_parsers.add_parser(
        "list",
        help="List multiple instances of test case, test cycle, or test executions from Zephyr Scale API",
    )
    sub_parse_list = parse_list.add_subparsers()
    sub_parse_list.required = True

    parse_test_executions = sub_parse_list.add_parser(
        "test_executions",
        help="List test executions from a Test Case or from a Test Cycle",
    )
    parse_test_executions.set_defaults(func=list_test_executions)
    parse_test_executions.add_argument(
        "key",
        type=str,
        help="Key associated with a test case or a test cycle. Ex.: BLOCK-T21 or BLOCK-R21.",
    )
    parse_test_executions.add_argument("-i", "--indent", type=int, default=4)
    parse_test_executions.add_argument("-m", "--max", type=int, default=20, help="")
    parse_test_executions.add_argument(
        "-o",
        "--only-last",
        action="store_true",
        help="List only the last test execution for each test case/cycle.",
    )
    parse_test_executions.add_argument(
        "-p", "--parse", choices=["raw", "full", "simple"], default="raw"
    )

    args = parser.parse_args()
    asyncio.run(args.func(**vars(args)))


def setup_zephyr_interface():
    """Setup Zephyr Scale API interface."""

    # Get Zephyr Scale API token
    zephyr_token = os.getenv("ZEPHYR_API_TOKEN")
    jira_token = os.getenv("JIRA_API_TOKEN")
    jira_username = os.getenv("JIRA_USERNAME")

    if zephyr_token is None:
        raise ValueError("ZEPHYR_API_TOKEN environment variable not set.")
    if jira_token is None:
        raise ValueError("JIRA_API_TOKEN environment variable not set.")
    if jira_username is None:
        raise ValueError("JIRA_USERNAME environment variable not set.")

    # TODO - The logging level seems to be stuck at WARNING.
    #   We need to investigate why the log level cannot be changed.
    #   It works if we change the log level to ERROR. But it does not work
    #   if we change it to DEBUG or INFO.
    log_level = logging.ERROR
    logger = logging.getLogger("ZephyrInterface")
    logger.setLevel(log_level)

    zapi = ZephyrInterface(
        zephyr_api_token=zephyr_token,
        jira_api_token=jira_token,
        jira_username=jira_username,
        log=logger,
    )

    return zapi
