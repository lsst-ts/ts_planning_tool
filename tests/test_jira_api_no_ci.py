import os
import unittest

import aiohttp
import pytest
from aiohttp import BasicAuth
from lsst.ts.planning.tool.zephyr_interface import SESSION_HEADERS, ZephyrInterface

JIRA_BASE_URL = "https://rubinobs.atlassian.net/rest/api/2/"


@pytest.mark.skipif(
    "JIRA_USERNAME" not in os.environ,
    reason="Skipping test because JIRA_USERNAME is not defined",
)
@pytest.mark.skipif(
    "JIRA_API_TOKEN" not in os.environ,
    reason="Skipping test because JIRA_API_TOKEN is not defined",
)
class TestJiraAPI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.jira_api_token = os.getenv("JIRA_API_TOKEN")
        self.jira_login = ZephyrInterface(
            jira_username=os.getenv("JIRA_USERNAME")
        ).jira_login

    @pytest.mark.asyncio
    async def test_jira_api_token(self):
        endpoint = "myself"
        url = f"{JIRA_BASE_URL}{endpoint}"

        async with aiohttp.ClientSession(
            auth=BasicAuth(self.jira_login, self.jira_api_token),
            raise_for_status=True,
            headers=SESSION_HEADERS,
        ) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    user_details = await response.json()
                    print("Token is working fine. User details:")
                    print(user_details)
                else:
                    print(f"Failed to authenticate. Status code: {response.status}")
                    print("Response:", await response.text())


if __name__ == "__main__":
    pytest.main()
