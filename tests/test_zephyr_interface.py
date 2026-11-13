import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from lsst.ts.planning.tool.zephyr_interface import (
    AddTestCasesError,
    ZephyrInterface,
    format_zephyr_date,
)


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

    def test_jira_login(self):
        self.zapi.jira_username = "jdoe@example.org"
        self.assertEqual(self.zapi.jira_login, "jdoe@example.org")
        self.zapi.jira_username = "jdoe"
        self.assertEqual(self.zapi.jira_login, "jdoe@lsst.org")
        self.zapi.jira_username = None
        self.assertIsNone(self.zapi.jira_login)

    @patch("aiohttp.ClientSession.get")
    async def test_get_list_of_statuses(self, mock_get):
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

        statuses = await self.zapi.get_list_of_statuses()
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
        test_case = await self.zapi.get_test_case(test_case_key)
        self.assertEqual(test_case["key"], test_case_key)
        self.assertListEqual(list(test_case.keys()), payload_expected_keys)

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
        test_cycle = await self.zapi.get_test_cycle(test_cycle_id, parse="raw")
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
    async def test_list_test_executions(self, mock_get):
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
        test_executions = await self.zapi.list_test_executions(test_cycle_key)
        self.assertListEqual(list(test_executions.keys()), payload_expected_keys)
        self.assertListEqual(
            list(test_executions["values"][0].keys()), values_expected_keys
        )

    @staticmethod
    def _page(values, start_at, max_results, total):
        """Build a mock response holding one page of a paginated payload."""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "next": None,
                "startAt": start_at,
                "maxResults": max_results,
                "total": total,
                "isLast": start_at + len(values) >= total,
                "values": values,
            }
        )
        return mock_response

    @patch("aiohttp.ClientSession.get")
    async def test_get_all(self, mock_get):
        # The server answers with a page size (2) smaller than requested (100).
        mock_get.return_value.__aenter__.side_effect = [
            self._page([1, 2], 0, 2, 5),
            self._page([3, 4], 2, 2, 5),
            self._page([5], 4, 2, 5),
        ]

        values = await self.zapi.get_all("testexecutions", {"testCycle": "BLOCK-R21"})

        self.assertListEqual(values, [1, 2, 3, 4, 5])
        requested = [
            (call.kwargs["params"]["startAt"], call.kwargs["params"]["maxResults"])
            for call in mock_get.call_args_list
        ]
        self.assertListEqual(requested, [(0, 100), (2, 2), (4, 2)])
        for call in mock_get.call_args_list:
            self.assertEqual(call.kwargs["params"]["testCycle"], "BLOCK-R21")

    @patch("aiohttp.ClientSession.get")
    async def test_get_all_stops_on_empty_page(self, mock_get):
        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value={"startAt": 0, "maxResults": 10, "isLast": False, "values": []}
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        self.assertListEqual(await self.zapi.get_all("testexecutions"), [])
        self.assertEqual(mock_get.call_count, 1)

    @staticmethod
    def _post_response(status=201, body=None, headers=None):
        """Build a mock response for a POST request."""
        mock_response = MagicMock()
        mock_response.status = status
        mock_response.reason = "Created" if status < 400 else "Error"
        mock_response.headers = headers or {}
        mock_response.json = AsyncMock(return_value=body)
        mock_response.text = AsyncMock(return_value=json.dumps(body))
        return mock_response

    @patch("aiohttp.ClientSession.post")
    async def test_post(self, mock_post):
        mock_response = self._post_response(body={"id": 1, "key": "BLOCK-R999"})
        mock_post.return_value.__aenter__.return_value = mock_response

        payload = {"projectKey": "BLOCK", "name": "A test cycle"}
        response = await self.zapi.post("testcycles", payload)

        self.assertEqual(response["key"], "BLOCK-R999")
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], self.zapi.zephyr_base_url + "testcycles")
        self.assertEqual(kwargs["json"], payload)
        self.assertEqual(
            kwargs["headers"]["Authorization"], f"Bearer {self.zephyr_api_token}"
        )

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.post")
    async def test_post_retries_when_rate_limited(self, mock_post, mock_sleep):
        mock_post.return_value.__aenter__.side_effect = [
            self._post_response(429, {"message": "slow down"}, {"Retry-After": "7"}),
            self._post_response(201, {"id": 5}),
        ]

        response = await self.zapi.post("testexecutions", {})

        self.assertEqual(response, {"id": 5})
        mock_sleep.assert_awaited_once_with(7.0)

    @patch("aiohttp.ClientSession.post")
    async def test_post_error_includes_body(self, mock_post):
        mock_post.return_value.__aenter__.return_value = self._post_response(
            400, {"message": "statusName does not exist"}
        )

        with self.assertRaises(aiohttp.ClientResponseError) as context:
            await self.zapi.post("testexecutions", {})

        self.assertEqual(context.exception.status, 400)
        self.assertIn("statusName does not exist", context.exception.message)

    def test_format_zephyr_date(self):
        chile = timezone(timedelta(hours=-3))
        self.assertEqual(
            format_zephyr_date(datetime(2026, 11, 16, 0, 0, tzinfo=chile)),
            "2026-11-16T03:00:00Z",
        )
        self.assertEqual(
            format_zephyr_date(datetime(2026, 11, 16, 3, 0)), "2026-11-16T03:00:00Z"
        )
        date = "2026-11-16T03:00:00Z"
        self.assertEqual(format_zephyr_date(date), date)
        self.assertIsNone(format_zephyr_date(None))

    @patch("aiohttp.ClientSession.post")
    async def test_create_test_cycle(self, mock_post):
        mock_post.return_value.__aenter__.return_value = self._post_response(
            body={"id": 1, "self": "...", "key": "BLOCK-R999"}
        )

        response = await self.zapi.create_test_cycle(
            "2026-11-16 LSST Survey Plan",
            description='<a href="https://example.org">notes</a>',
            planned_start_date=datetime(2026, 11, 16, 3, tzinfo=timezone.utc),
            planned_end_date="2026-11-17T03:00:00Z",
            folder_id=61514676,
            owner_id="abc-123",
        )

        self.assertEqual(response["key"], "BLOCK-R999")
        self.assertEqual(
            mock_post.call_args.args[0], self.zapi.zephyr_base_url + "testcycles"
        )
        self.assertDictEqual(
            mock_post.call_args.kwargs["json"],
            {
                "projectKey": "BLOCK",
                "name": "2026-11-16 LSST Survey Plan",
                "description": '<a href="https://example.org">notes</a>',
                "plannedStartDate": "2026-11-16T03:00:00Z",
                "plannedEndDate": "2026-11-17T03:00:00Z",
                "folderId": 61514676,
                "ownerId": "abc-123",
            },
        )

    @patch("aiohttp.ClientSession.post")
    async def test_add_test_cases_to_cycle(self, mock_post):
        mock_post.return_value.__aenter__.side_effect = [
            self._post_response(body={"id": 11}),
            self._post_response(body={"id": 12}),
        ]

        added = await self.zapi.add_test_cases_to_cycle(
            "BLOCK-R999",
            ["BLOCK-T20", {"key": "BLOCK-T594", "environment": "1. Daytime"}],
        )

        self.assertListEqual(
            added,
            [
                {"key": "BLOCK-T20", "environment": None, "id": 11},
                {"key": "BLOCK-T594", "environment": "1. Daytime", "id": 12},
            ],
        )
        payloads = [call.kwargs["json"] for call in mock_post.call_args_list]
        self.assertDictEqual(
            payloads[0],
            {
                "projectKey": "BLOCK",
                "testCycleKey": "BLOCK-R999",
                "testCaseKey": "BLOCK-T20",
                "statusName": "Not Executed",
                "automated": False,
            },
        )
        self.assertEqual(payloads[1]["testCaseKey"], "BLOCK-T594")
        self.assertEqual(payloads[1]["environmentName"], "1. Daytime")

    @patch("aiohttp.ClientSession.post")
    async def test_add_test_cases_to_cycle_stops_on_error(self, mock_post):
        mock_post.return_value.__aenter__.side_effect = [
            self._post_response(body={"id": 11}),
            self._post_response(400, {"message": "call to test not supported"}),
        ]

        with self.assertRaises(AddTestCasesError) as context:
            await self.zapi.add_test_cases_to_cycle(
                "BLOCK-R999", ["BLOCK-T20", "BLOCK-T250", "BLOCK-T594"]
            )

        self.assertEqual(context.exception.failed_key, "BLOCK-T250")
        added_keys = [item["key"] for item in context.exception.added]
        self.assertListEqual(added_keys, ["BLOCK-T20"])
        self.assertIn("call to test", context.exception.__cause__.message)
        self.assertEqual(mock_post.call_count, 2)

    async def test_add_test_cases_to_cycle_invalid_key(self):
        with self.assertRaises(ValueError):
            await self.zapi.add_test_cases_to_cycle("BLOCK-T21", ["BLOCK-T20"])

    def _mock_folders(self, mock_get):
        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value=load_json_data("folders_test_cycle.json")
        )
        mock_get.return_value.__aenter__.return_value = mock_response

    @patch("aiohttp.ClientSession.post")
    @patch("aiohttp.ClientSession.get")
    async def test_get_or_create_folder_found(self, mock_get, mock_post):
        self._mock_folders(mock_get)

        result = await self.zapi.get_or_create_folder("/LSST Survey Plans/2026/week46")

        self.assertEqual(result, (61514676, "found"))
        params = mock_get.call_args.kwargs["params"]
        self.assertEqual(params["folderType"], "TEST_CYCLE")
        mock_post.assert_not_called()

    @patch("aiohttp.ClientSession.post")
    @patch("aiohttp.ClientSession.get")
    async def test_get_or_create_folder_dry_run(self, mock_get, mock_post):
        self._mock_folders(mock_get)

        result = await self.zapi.get_or_create_folder(
            "/LSST Survey Plans/2026/week47", dry_run=True
        )

        self.assertEqual(result, (None, "missing"))
        mock_post.assert_not_called()

    @patch("aiohttp.ClientSession.post")
    @patch("aiohttp.ClientSession.get")
    async def test_get_or_create_folder_created(self, mock_get, mock_post):
        self._mock_folders(mock_get)
        mock_post.return_value.__aenter__.return_value = self._post_response(
            body={"id": 99, "self": "..."}
        )

        result = await self.zapi.get_or_create_folder("/LSST Survey Plans/2026/week47")

        self.assertEqual(result, (99, "created"))
        self.assertDictEqual(
            mock_post.call_args.kwargs["json"],
            {
                "parentId": 57322463,
                "name": "week47",
                "projectKey": "BLOCK",
                "folderType": "TEST_CYCLE",
            },
        )

    @patch("aiohttp.ClientSession.post")
    @patch("aiohttp.ClientSession.get")
    async def test_get_or_create_folder_missing_parent(self, mock_get, mock_post):
        self._mock_folders(mock_get)

        with self.assertRaises(ValueError):
            await self.zapi.get_or_create_folder("/LSST Survey Plans/2027/week01")
        mock_post.assert_not_called()

    @patch("aiohttp.ClientSession.get")
    async def test_get_myself(self, mock_get):
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"accountId": "abc-123"})
        mock_get.return_value.__aenter__.return_value = mock_response

        myself = await self.zapi.get_myself()

        self.assertEqual(myself["accountId"], "abc-123")
        self.assertEqual(mock_get.call_args.args[0], self.zapi.jira_base_url + "myself")

    @patch("aiohttp.ClientSession.get")
    async def test_list_test_cases_in_cycle(self, mock_get):
        executions = load_json_data("test_executions.json")["values"]
        # Split the recorded payload in two pages and repeat one test case, to
        # check both the pagination and the de-duplication.
        executions.append(executions[0])
        total = len(executions)
        mock_get.return_value.__aenter__.side_effect = [
            self._page(executions[:10], 0, 10, total),
            self._page(executions[10:], 10, 10, total),
        ]

        test_cases = await self.zapi.list_test_cases_in_cycle("BLOCK-R21")
        test_case_keys = [test_case["key"] for test_case in test_cases]

        expected = []
        for execution in executions:
            key = execution["testCase"]["self"].split("/testcases/")[1].split("/")[0]
            if key not in expected:
                expected.append(key)
        self.assertListEqual(test_case_keys, expected)
        self.assertDictEqual(
            test_cases[0],
            {"key": "BLOCK-T18", "version": 1, "environmentId": 6824992},
        )
        self.assertLess(len(test_case_keys), total)
        self.assertEqual(mock_get.call_count, 2)

    @patch("aiohttp.ClientSession.get")
    async def test_get_environments(self, mock_get):
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=load_json_data("environments.json"))
        mock_get.return_value.__aenter__.return_value = mock_response

        environments = await self.zapi.get_environments()

        names = {environment["name"].strip() for environment in environments}
        self.assertIn("1. Daytime", names)
        self.assertIn("8. Closed Dome", names)
        self.assertEqual(mock_get.call_args.kwargs["params"]["projectKey"], "BLOCK")

    async def test_list_test_cases_in_cycle_invalid_key(self):
        with self.assertRaises(ValueError):
            await self.zapi.list_test_cases_in_cycle("BLOCK-T21")

    @patch("aiohttp.ClientSession.get")
    async def test_parse(self, mock_get):
        status_id = 10001
        status_name = "In Progress"

        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"name": status_name})

        mock_get.return_value.__aenter__.return_value = mock_response

        status = await self.zapi.parse(
            {"self": f"http://localhost:8080/rest/api/2/status/{status_id}"}
        )
        self.assertEqual(status["name"], status_name)

    @patch("aiohttp.ClientSession.get")
    async def test_parse_environment(self, mock_get):
        environment_id = 10000
        environment_name = "Test Environment"

        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"name": environment_name})

        mock_get.return_value.__aenter__.return_value = mock_response

        environment = await self.zapi.parse(
            {"self": f"http://localhost:8080/rest/api/2/environment/{environment_id}"}
        )

        self.assertEqual(environment["name"], environment_name)

    @patch("aiohttp.ClientSession.get")
    async def test_parse_project(self, mock_get):
        project_id = 10000
        project_key = "BLOCK"

        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"key": project_key})

        mock_get.return_value.__aenter__.return_value = mock_response

        project = await self.zapi.parse(
            {"self": f"http://localhost:8080/rest/api/2/project/{project_id}"}
        )

        self.assertEqual(project["key"], project_key)

    @patch("aiohttp.ClientSession.get")
    async def test_parse_status(self, mock_get):
        status_id = 10001
        status_name = "In Progress"

        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"name": status_name})

        mock_get.return_value.__aenter__.return_value = mock_response

        status = await self.zapi.parse(
            {"self": f"http://localhost:8080/rest/api/2/status/{status_id}"}
        )

        self.assertEqual(status["name"], status_name)

    @patch("aiohttp.ClientSession.get")
    async def test_parse_priority(self, mock_get):
        priority_id = 10001
        priority_key = "3"

        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"key": priority_key})

        mock_get.return_value.__aenter__.return_value = mock_response

        priority = await self.zapi.parse(
            {"self": f"http://localhost:8080/rest/api/2/priority/{priority_id}"}
        )

        self.assertEqual(priority["key"], priority_key)

    @patch("aiohttp.ClientSession.get")
    async def test_parse_test_cycle(self, mock_get):
        test_cycle_id = 10000
        test_cycle_key = "BLOCK-R21"

        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"key": test_cycle_key})

        mock_get.return_value.__aenter__.return_value = mock_response

        test_cycle = await self.zapi.parse(
            {"self": f"http://localhost:8080/rest/api/2/testcycle/{test_cycle_id}"}
        )

        self.assertEqual(test_cycle["key"], test_cycle_key)


if __name__ == "__main__":
    unittest.main()
