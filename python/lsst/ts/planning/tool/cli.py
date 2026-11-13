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
import re
import sys

from lsst.ts.planning.tool.weekly_draft import DraftWeekError, draft_week, format_report
from lsst.ts.planning.tool.zephyr_interface import AddTestCasesError, ZephyrInterface


async def draft_week_command(
    plan_file, execute=False, output_json=False, verbose=False, **kwargs
):
    """Draft the test cycles of a week from a JSON plan (dry run by default)."""
    with open(plan_file, "r") as file:
        plan = json.load(file)

    zapi = setup_zephyr_interface()
    zapi.log.setLevel(logging.INFO if verbose else logging.WARNING)

    try:
        report = await draft_week(zapi, plan, dry_run=not execute)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
    except DraftWeekError as error:
        print(format_report(error.report))
        print(f"\nERROR: {error}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(report, indent=4) if output_json else format_report(report))


async def add_test_cases_command(
    test_cycle_key,
    test_case_keys,
    environment=None,
    execute=False,
    verbose=False,
    **kwargs,
):
    """Add test cases to the end of a test cycle (dry run by default)."""
    test_cases = [{"key": key, "environment": environment} for key in test_case_keys]
    if not execute:
        print("DRY RUN: nothing was written. Add --execute to add the test cases.")
        where = environment or "no environment"
        for test_case in test_cases:
            print(f"  would add {test_case['key']} to {test_cycle_key} ({where})")
        return

    zapi = setup_zephyr_interface()
    zapi.log.setLevel(logging.INFO if verbose else logging.WARNING)
    try:
        added = await zapi.add_test_cases_to_cycle(test_cycle_key, test_cases)
    except AddTestCasesError as error:
        print(f"ERROR: {error} ({error.__cause__.message})", file=sys.stderr)
        sys.exit(1)
    for item in added:
        print(f"  added {item['key']} to {test_cycle_key} (execution id {item['id']})")


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


async def get_steps(test_key, indent=4, complement=True, **kwargs):
    """Get steps in a test case or test execution from Zephyr Scale API.

    The test key pattern determines which Zephyr Scale endpoint is queried:
    a test case (e.g. ``BLOCK-T00``) or a test execution (e.g. ``BLOCK-E000``).
    """
    zapi = setup_zephyr_interface()
    if re.search(r"(.+-T[0-9]+)", test_key):
        test_steps = await zapi.get_steps_in_test_case(
            test_key, call_to_test=complement
        )
    elif re.search(r"(.+-E[0-9]+)", test_key):
        test_steps = await zapi.get_steps_in_test_execution(test_key)
    else:
        raise ValueError(
            "Invalid test key. Expected a test case (e.g. BLOCK-T00) or a "
            "test execution (e.g. BLOCK-E000)."
        )
    print(json.dumps(test_steps, indent=indent))


async def get_user(user_id, indent=4, **kwargs):
    """Get the user name based on its Jira ID number."""
    zapi = setup_zephyr_interface()
    user_name = await zapi.get_user_name(user_id)
    print(json.dumps(user_name, indent=indent))


async def list_test_executions(
    key, indent=4, max_results=5, only_last=False, parse="raw", verbose=False, **kwargs
):
    """List test executions for a test cycle or a test case from Zephyr Scale
    API."""
    zapi = setup_zephyr_interface()
    zapi.log.setLevel(logging.DEBUG if verbose else logging.ERROR)
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
    parse_test_steps.set_defaults(func=get_steps)
    parse_test_steps.add_argument(
        "test_key",
        type=str,
        help="Key associated with a test case (e.g. BLOCK-T00) or a test execution (e.g. BLOCK-E000).",
    )
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
    parse_test_executions.add_argument(
        "-v", "--verbose", action="store_true", help="Print verbose output."
    )

    parse_draft = sub_parsers.add_parser(
        "draft",
        help="Draft test cycles in Zephyr Scale from a plan",
    )
    sub_parse_draft = parse_draft.add_subparsers()
    sub_parse_draft.required = True

    parse_draft_week = sub_parse_draft.add_parser(
        "week",
        help="Draft the nightly test cycles of a week from a JSON plan. "
        "Dry run unless --execute is given.",
    )
    parse_draft_week.set_defaults(func=draft_week_command)
    parse_draft_week.add_argument("plan_file", type=str, help="Path to the JSON plan.")
    parse_draft_week.add_argument(
        "--execute",
        action="store_true",
        help="Create the folder, test cycles and test executions in Zephyr Scale.",
    )
    parse_draft_week.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Print the report as JSON.",
    )
    parse_draft_week.add_argument(
        "-v", "--verbose", action="store_true", help="Print every request."
    )

    parse_add = sub_parsers.add_parser(
        "add",
        help="Add items to an existing Zephyr Scale entity",
    )
    sub_parse_add = parse_add.add_subparsers()
    sub_parse_add.required = True

    parse_add_test_cases = sub_parse_add.add_parser(
        "test_cases",
        help="Add test cases to the end of a test cycle. "
        "Dry run unless --execute is given.",
    )
    parse_add_test_cases.set_defaults(func=add_test_cases_command)
    parse_add_test_cases.add_argument(
        "test_cycle_key", type=str, help="e.g. BLOCK-R760"
    )
    parse_add_test_cases.add_argument(
        "test_case_keys", type=str, nargs="+", help="e.g. BLOCK-T724 BLOCK-T563"
    )
    parse_add_test_cases.add_argument(
        "-e", "--environment", type=str, default=None, help="e.g. '6. Night'"
    )
    parse_add_test_cases.add_argument(
        "--execute", action="store_true", help="Add the test cases in Zephyr Scale."
    )
    parse_add_test_cases.add_argument(
        "-v", "--verbose", action="store_true", help="Print every request."
    )

    args = parser.parse_args()
    asyncio.run(args.func(**vars(args)))


def setup_logging():
    """
    Set up logging for the ZephyrInterface.
    This function configures a logger named "ZephyrInterface" to log messages
    at the DEBUG level. It creates a console handler that outputs log messages
    to the standard output stream and formats the log messages with a specific
    format that includes the timestamp, logger name, log level, and message.

    Returns
    -------
    logging.Logger
        The configured logger instance.
    """
    log_level = logging.DEBUG
    logger = logging.getLogger("ZephyrInterface")
    logger.setLevel(log_level)

    # Create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Add formatter to ch
    ch.setFormatter(formatter)

    # Add ch to logger
    logger.addHandler(ch)

    return logger


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
    logger = setup_logging()

    zapi = ZephyrInterface(
        zephyr_api_token=zephyr_token,
        jira_api_token=jira_token,
        jira_username=jira_username,
        log=logger,
    )

    return zapi
