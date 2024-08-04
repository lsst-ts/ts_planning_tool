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

import json
import os
import unittest

import pytest
from lsst.ts.planning.tool.zephyr_interface import ZephyrInterface


@pytest.mark.skipif(
    "ZEPHYR_API_TOKEN" not in os.environ,
    reason="Skipping test because ZEPHYR_API_TOKEN is not defined",
)
@pytest.mark.skipif(
    "JIRA_API_TOKEN" not in os.environ,
    reason="Skipping test because JIRA_API_TOKEN is not defined",
)
@pytest.mark.skipif(
    "JIRA_USERNAME" not in os.environ,
    reason="Skipping test because JIRA_USERNAME is not defined",
)
class TestZephyrInterfaceWithRealData(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.jira_api_token = os.getenv("JIRA_API_TOKEN")
        self.jira_username = os.getenv("JIRA_USERNAME")
        self.zephyr_api_token = os.getenv("ZEPHYR_API_TOKEN")

        self.zapi = ZephyrInterface(
            jira_api_token=self.jira_api_token,
            jira_username=self.jira_username,
            zephyr_api_token=self.zephyr_api_token,
        )

    def test_init(self):
        self.assertEqual(self.zapi.jira_username, self.jira_username)
        self.assertEqual(self.zapi.jira_api_token, self.jira_api_token)
        self.assertEqual(self.zapi.zephyr_api_token, self.zephyr_api_token)

    @pytest.mark.asyncio
    async def test_get_statuses(self):

        payload_expected_keys = [
            "next",
            "startAt",
            "maxResults",
            "total",
            "isLast",
            "values",
        ]

        statuses = await self.zapi.get_statuses()
        self.assertListEqual(list(statuses.keys()), payload_expected_keys)

    @pytest.mark.asyncio
    async def test_get_test_case(self):

        payload_expected_keys = [
            "id",
            "key",
            "name",
            "project",
            "createdOn",
            "objective",
            "precondition",
            "estimatedTime",
            "labels",
            "component",
            "priority",
            "status",
            "folder",
            "owner",
            "testScript",
            "customFields",
            "links",
        ]

        test_case_key = "BLOCK-T21"
        test_case = await self.zapi.get_test_case(test_case_key)
        self.assertEqual(test_case["key"], test_case_key)
        self.assertListEqual(list(test_case.keys()), payload_expected_keys)

    async def test_get_test_case_steps(self):

        payload_expected_keys = [
            "next",
            "startAt",
            "maxResults",
            "total",
            "isLast",
            "values",
        ]
        payload_value_keys = ["inline", "testCase"]

        test_case_key = "BLOCK-T21"
        test_case_steps = await self.zapi.get_test_case_steps(test_case_key)
        self.assertListEqual(list(test_case_steps.keys()), payload_expected_keys)
        self.assertListEqual(
            list(test_case_steps["values"][0].keys()), payload_value_keys
        )

    async def test_get_test_execution(self):

        payload_expected_keys = [
            "id",
            "key",
            "project",
            "testCase",
            "environment",
            "jiraProjectVersion",
            "testExecutionStatus",
            "actualEndDate",
            "estimatedTime",
            "executionTime",
            "executedById",
            "assignedToId",
            "comment",
            "automated",
            "testCycle",
            "customFields",
            "links",
        ]

        test_execution_id = "BLOCK-E192"
        test_execution = await self.zapi.get_test_execution(test_execution_id)
        self.assertListEqual(list(test_execution.keys()), payload_expected_keys)
        self.assertEqual(test_execution["key"], test_execution_id)

    async def test_extract_test_case_from_test_execution(self):

        expected_test_case_name = "BLOCK-T21"
        expected_test_case_version = "1"

        test_execution_id = "BLOCK-E192"
        test_execution = await self.zapi.get_test_execution(test_execution_id)
        test_case_name, test_case_version = (
            self.zapi.extract_test_case_from_test_execution(test_execution)
        )

        self.assertEqual(test_case_name, expected_test_case_name)
        self.assertEqual(test_case_version, expected_test_case_version)

    async def test_get_test_executions(self):

        payload_expected_keys = [
            "next",
            "startAt",
            "maxResults",
            "total",
            "isLast",
            "values",
        ]

        values_expected_keys = [
            "id",
            "key",
            "project",
            "testCase",
            "environment",
            "jiraProjectVersion",
            "testExecutionStatus",
            "actualEndDate",
            "estimatedTime",
            "executionTime",
            "executedById",
            "assignedToId",
            "comment",
            "automated",
            "testCycle",
            "customFields",
            "links",
        ]

        test_cycle_key = "BLOCK-R21"
        test_executions = await self.zapi.get_test_executions(test_cycle_key)
        self.assertListEqual(list(test_executions.keys()), payload_expected_keys)
        self.assertListEqual(
            list(test_executions["values"][0].keys()), values_expected_keys
        )

    async def test_parse_project_from_id(self):

        project_id = 350001  # BLOCK project id
        project = await self.zapi.parse_project_from_id(project_id)
        self.assertEqual(project, "BLOCK")

    async def test_parse_status_from_id(self):

        status_id = 3940035  # Pass status id
        status = await self.zapi.parse_status_from_id(status_id)
        self.assertEqual(status, "Pass")


if __name__ == "__main__":
    pytest.main()
