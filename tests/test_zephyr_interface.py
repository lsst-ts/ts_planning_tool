import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from lsst.ts.planning.tool.zephyr_interface import ZephyrInterface


def load_json_data(filename):
    import json
    import os

    filepath = os.path.join(os.path.dirname(__file__), "data", filename)
    with open(filepath, "r") as file:
        return json.load(file)


class TestZephyrInterface(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.jira_api_token = "test_token"
        self.jira_username = "test_username"
        self.zephyr_api_token = "test_token"
        self.zapi = ZephyrInterface(
            jira_api_token=self.jira_api_token,
            jira_username=self.jira_username,
            zephyr_api_token=self.zephyr_api_token,
        )

    def test_init(self):
        self.assertEqual(self.zapi.jira_username, self.jira_username)
        self.assertEqual(self.zapi.jira_api_token, self.jira_api_token)
        self.assertEqual(self.zapi.zephyr_api_token, self.zephyr_api_token)

    @patch("aiohttp.ClientSession.get")
    async def test_get_statuses(self, mock_get):

        payload_expected_keys = [
            "next",
            "startAt",
            "maxResults",
            "total",
            "isLast",
            "values",
        ]

        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=load_json_data("statuses.json"))

        mock_get.return_value.__aenter__.return_value = mock_response

        statuses = await self.zapi.get_statuses()
        self.assertListEqual(list(statuses.keys()), payload_expected_keys)

    @patch("aiohttp.ClientSession.get")
    async def test_get_test_case(self, mock_get):

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

        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=load_json_data("test_case.json"))

        mock_get.return_value.__aenter__.return_value = mock_response

        test_case_key = "BLOCK-T21"
        test_case = await self.zapi.get_test_case(test_case_key, raw=True)
        self.assertEqual(test_case["key"], test_case_key)
        self.assertListEqual(list(test_case.keys()), payload_expected_keys)

    @patch("aiohttp.ClientSession.get")
    async def test_get_test_cycle(self, mock_get):

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

        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=load_json_data("test_cycle.json"))

        mock_get.return_value.__aenter__.return_value = mock_response

        test_cycle_key = "BLOCK-R21"
        test_cycle = await self.zapi.get_test_cycle(test_cycle_key, raw=True)
        self.assertEqual(test_cycle["key"], test_cycle_key)
        self.assertListEqual(list(test_cycle.keys()), payload_expected_keys)

    @patch("aiohttp.ClientSession.get")
    async def test_get_steps_in_test_case(self, mock_get):

        payload_expected_keys = [
            "next",
            "startAt",
            "maxResults",
            "total",
            "isLast",
            "values",
        ]

        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value=load_json_data("test_case_steps.json")
        )

        mock_get.return_value.__aenter__.return_value = mock_response

        test_case_key = "BLOCK-T21"
        test_case_steps = await self.zapi.get_steps_in_test_case(test_case_key)
        self.assertListEqual(list(test_case_steps.keys()), payload_expected_keys)

    @patch("aiohttp.ClientSession.get")
    async def test_get_test_cycle(self, mock_get):

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

        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=load_json_data("test_cycle.json"))

        mock_get.return_value.__aenter__.return_value = mock_response

        test_cycle_id = "BLOCK-R21"
        test_cycle = await self.zapi.get_test_cycle(test_cycle_id)
        self.assertEqual(test_cycle["key"], test_cycle_id)
        self.assertListEqual(list(test_cycle.keys()), payload_expected_keys)

    @patch("aiohttp.ClientSession.get")
    async def test_get_test_execution(self, mock_get):

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

        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value=load_json_data("test_execution.json")
        )

        mock_get.return_value.__aenter__.return_value = mock_response

        test_execution_id = "BLOCK-E192"
        test_execution = await self.zapi.get_test_execution(test_execution_id)
        self.assertEqual(test_execution["key"], test_execution_id)
        self.assertListEqual(list(test_execution.keys()), payload_expected_keys)

    @patch("aiohttp.ClientSession.get")
    async def test_get_test_executions(self, mock_get):

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

        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value=load_json_data("test_executions.json")
        )

        mock_get.return_value.__aenter__.return_value = mock_response

        test_cycle_key = "BLOCK-R21"
        test_executions = await self.zapi.get_test_executions(test_cycle_key)
        self.assertListEqual(list(test_executions.keys()), payload_expected_keys)
        self.assertListEqual(
            list(test_executions["values"][0].keys()), values_expected_keys
        )

    @patch("aiohttp.ClientSession.get")
    async def test_parse_environment_from_id(self, mock_get):
        environment_id = 20001
        environment_name = "Production"
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"name": environment_name})

        mock_get.return_value.__aenter__.return_value = mock_response

        environment = await self.zapi.parse_environment_from_id(environment_id)
        self.assertEqual(environment, environment_name)

    @patch("aiohttp.ClientSession.get")
    async def test_parse_project_from_id(self, mock_get):

        project_key = "TEST"
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"key": project_key})

        mock_get.return_value.__aenter__.return_value = mock_response

        project_id = 10000
        project = await self.zapi.parse_project_from_id(project_id)
        self.assertIsInstance(project, str)

    @patch("aiohttp.ClientSession.get")
    async def test_parse_status_from_id(self, mock_get):
        status_id = 10001
        status_name = "In Progress"
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"name": status_name})

        mock_get.return_value.__aenter__.return_value = mock_response

        status = await self.zapi.parse_status_from_id(status_id)
        self.assertEqual(status, status_name)

    @patch("aiohttp.ClientSession.get")
    async def test_parse_test_cycle_from_id(self, mock_get):

        test_cycle_id = 20001
        test_cycle_name = "Cycle 1"
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"key": test_cycle_name})

        mock_get.return_value.__aenter__.return_value = mock_response

        test_cycle = await self.zapi.parse_test_cycle_from_id(test_cycle_id)
        self.assertEqual(test_cycle, test_cycle_name)


if __name__ == "__main__":
    unittest.main()
