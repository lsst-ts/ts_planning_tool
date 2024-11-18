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

import os
import unittest

import pytest
from lsst.ts.planning.tool.zephyr_interface import ZephyrInterface

# Real data from Zephyr
ENVIRONMENT = {
    "id": 6824992,
    "name": "1. Daytime",
    "self": "https://api.zephyrscale.smartbear.com/v2/environments/6824992",
}
PRIORITY = {
    "id": 6360096,
    "key": "Normal",
    "self": "https://api.zephyrscale.smartbear.com/v2/priorities/6360096",
}
PROJECT = {
    "id": 350001,
    "key": "BLOCK",
    "self": "https://api.zephyrscale.smartbear.com/v2/projects/350001",
}
STATUS = {
    "id": 3940035,
    "name": "Pass",
    "self": "https://api.zephyrscale.smartbear.com/v2/statuses/3940035",
}
TEST_CYCLE = {
    "id": 22355742,
    "key": "BLOCK-R21",
    "self": "https://api.zephyrscale.smartbear.com/v2/testcycles/22355742",
}


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

    # TODO (b1quint): Implement feature
    # @pytest.mark.asyncio
    # async def test_extract_test_case_from_test_execution(self):

    #     expected_test_case_name = "BLOCK-T21"
    #     expected_test_case_version = "1"

    #     test_execution_id = "BLOCK-E192"
    #     test_execution = \
    #         await self.zapi.get_test_execution(test_execution_id)
    #     test_case_name, test_case_version = (
    #         self.zapi.extract_test_case_from_test_execution(test_execution)
    #     )

    #     self.assertEqual(test_case_name, expected_test_case_name)
    #     self.assertEqual(test_case_version, expected_test_case_version)

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

        statuses = await self.zapi.get_list_of_statuses()
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

    @pytest.mark.asyncio
    async def test_get_test_cycle(self):

        payload_expected_keys = [
            "id",
            "key",
            "name",
            "project",
            "jiraProjectVersion",
            "status",
            "folder",
            "description",
            "plannedStartDate",
            "plannedEndDate",
            "owner",
            "customFields",
            "links",
        ]

        test_cycle_key = "BLOCK-R21"
        test_cycle = await self.zapi.get_test_cycle(test_cycle_key)
        self.assertEqual(test_cycle["key"], test_cycle_key)
        self.assertListEqual(list(test_cycle.keys()), payload_expected_keys)

    @pytest.mark.asyncio
    async def test_get_steps_in_test_case(self):

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
        test_case_steps = await self.zapi.get_steps(test_case_key)
        self.assertListEqual(list(test_case_steps.keys()), payload_expected_keys)
        self.assertListEqual(
            list(test_case_steps["values"][0].keys()), payload_value_keys
        )

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_list_test_executions(self):

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
        test_executions = await self.zapi.list_test_executions(test_cycle_key)
        self.assertListEqual(list(test_executions.keys()), payload_expected_keys)
        self.assertListEqual(
            list(test_executions["values"][0].keys()), values_expected_keys
        )

    @pytest.mark.asyncio
    async def test_parse_environment(self):
        environment = await self.zapi.parse(ENVIRONMENT)
        self.assertEqual(environment["name"], ENVIRONMENT["name"])

    @pytest.mark.asyncio
    async def test_parse_project(self):
        project = await self.zapi.parse(PROJECT)
        self.assertEqual(project["key"], PROJECT["key"])

    @pytest.mark.asyncio
    async def test_parse_status(self):
        status = await self.zapi.parse(STATUS)
        self.assertEqual(status["name"], STATUS["name"])

    @pytest.mark.asyncio
    async def test_parse_priority(self):
        priority = await self.zapi.parse(PRIORITY)
        self.assertEqual(priority["key"], PRIORITY["key"])

    @pytest.mark.asyncio
    async def test_parse_test_cycle(self):
        test_cycle = await self.zapi.parse(TEST_CYCLE)
        self.assertEqual(test_cycle["key"], TEST_CYCLE["key"])


if __name__ == "__main__":
    pytest.main()
