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

__all__ = [
    "ZephyrInterface",
    "run_zephyr_interface",
]

import asyncio
import json
import logging
import os

import aiohttp
from aiohttp import BasicAuth

# Your JIRA Cloud base URL
ZEPHYR_BASE_URL = "https://api.zephyrscale.smartbear.com/v2/"
JIRA_BASE_URL = "https://rubinobs.atlassian.net/rest/api/2/"


class ZephyrInterface:
    """
    Jira Zephyr Scale API Interface
    https://support.smartbear.com/zephyr-scale-cloud/api-docs/

    This class provides an interface to the Zephyr Scale API.
    It allows you to query test cases, test steps, test executions,
    test cycles, and test plans. You can also update the status of a test
    execution.

    You will need to create two API tokens. One for your Jira Cloud account and
    another for Zephyr Scale. You can create an API token for your Jira Cloud
    account by accessing the following URL:
        https://id.atlassian.com/manage-profile/security/api-tokens

    Use the URL below to create an API token for Zephyr Scale:
        https://rubinobs.atlassian.net/plugins/servlet/ac/com.kanoah.test-manager/api-access-tokens

    Then, store the API tokens inside the JIRA_API_TOKEN and ZEPHYR_API_TOKEN
    environment variables. You will also want to store your username in the
    ZEPHYR_USERNAME and in the JIRA_USERNAME environment variables.

    Parameters
    ----------
    api_token : str
        The API token for authentication.
    base_url : str
        The base URL of the Jira instance.
    log : logging.Logger
        The logger object to use for logging.

    Attributes
    ----------
    api_token : str
        The API token for authentication.
    base_url : str
        The base URL of the Jira instance.
    """

    def __init__(
        self,
        jira_api_token=None,
        jira_base_url=JIRA_BASE_URL,
        jira_username=None,
        zephyr_api_token=None,
        zephyr_base_url=ZEPHYR_BASE_URL,
        log=None,
    ):
        self.jira_api_token = jira_api_token
        self.jira_base_url = jira_base_url
        self.jira_username = jira_username
        self.zephyr_api_token = zephyr_api_token
        self.zephyr_base_url = zephyr_base_url

        self.log = (
            logging.getLogger(type(self).__name__)
            if log is None
            else log.getChild(type(self).__name__)
        )

    @staticmethod
    def extract_test_case_from_test_execution(test_execution_json):
        """
        Extracts the test case name and version from the given test execution
        JSON.

        Parameters
        ----------
        test_execution_json : dict
            The JSON object representing the test execution.

        Returns
        -------
        tuple
            A tuple containing the test case name and version extracted from
            the test execution JSON.
        """
        url = test_execution_json.get("testCase").get("self")
        test_case_name = url.split("/")[-3]
        test_case_version = url.split("/")[-1]
        return test_case_name, test_case_version

    async def get_test_case(self, test_case_key):
        """
        Get the details of a test case.

        Parameters
        ----------
        test_case_key : str
            The key of the test case.

        Returns
        -------
        dict
            A dictionary containing the details of the test case.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Test-Cases/operation/getTestCase
        """
        endpoint = f"testcases/{test_case_key}"
        url = self.zephyr_base_url + endpoint

        headers = {
            "Authorization": f"Bearer {self.zephyr_api_token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(url=url, headers=headers) as response:
                values: dict = await response.json()
                self.log.debug(
                    f"Querying test case {test_case_key}. Got response: {values=}"
                )
                return values

    async def get_test_case_steps(self, test_case_key):
        """
        Get all the steps in a test case.

        Parameters
        ----------
        test_case_key : str
            The key of the test case.

        Returns
        -------
        dict
            A dictionary containing the steps of the test case.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Test-Cases/operation/getTestCaseTestSteps
        """
        endpoint = f"testcases/{test_case_key}/teststeps"
        url = self.zephyr_base_url + endpoint
        headers = {
            "Authorization": f"Bearer {self.zephyr_api_token}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            response = await session.get(url, headers=headers)
            steps = await response.json()
            return steps

    async def get_test_cycle(self, test_cycle_key):
        """
        Get the details of a test cycle.

        Parameters
        ----------
        test_cycle_key : str
            The key of the test cycle.

        Returns
        -------
        dict
            A dictionary containing the details of the test cycle.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Test-Cycles/operation/getTestCycle
        """
        endpoint = f"testcycles/{test_cycle_key}"
        url = self.zephyr_base_url + endpoint
        headers = {
            "Authorization": f"Bearer {self.zephyr_api_token}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(url=url, headers=headers) as response:
                values: dict = await response.json()
                self.log.debug(
                    f"Querying test cycle {test_cycle_key}. Got response: {values=}"
                )

        values["project"] = await self.get_project(values["project"]["id"])
        values["status"] = await self.get_status(values["status"]["id"])
        values["owner"] = await self.get_user_name(values["owner"]["accountId"])

        return values

    async def get_test_cycles(
        self, cycle_keys=None, max_results=20, start_at=0, project_key="BLOCK"
    ):
        """
        Get all the test cycles.

        Parameters
        ----------
        cycle_keys : dict, optional
            A dictionary containing the query parameters.
        max_results : int, optional
            The maximum number of test cycles to return. Default: 20
        start_at : int, optional
            The index of the first test cycle to return. The default is 0.
            Should be a multiple of maxResults. Default: 0
        project_key : str, optional
            The key of the Jira project. The default is "BLOCK".

        Returns
        -------
        dict
            A dictionary containing the test cycles.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Test-Cycles/operation/listTestCycles
        """
        # Check if start_at is a multiple of max_results
        if start_at % max_results != 0:
            raise ValueError("startAt must be a multiple of maxResults")

        # Prepare the query
        endpoint = "testcycles"
        url = self.zephyr_base_url + endpoint
        headers = {
            "Authorization": f"Bearer {self.zephyr_api_token}",
            "Content-Type": "application/json",
        }
        query_parameters = {
            "maxResults": max_results,
            "startAt": start_at,
            "projectKey": project_key,
        }

        # Perform the query
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(
                url=url, headers=headers, params=query_parameters
            ) as response:

                if response.status == 200:
                    test_cycles = await response.json()
                    # We are only interested in the list of test cycles
                    test_cycles = test_cycles["values"]
                else:
                    raise aiohttp.ClientError(
                        f"Failed to query test cycles. Status code: {response.status}"
                    )

        # Check if the query keys are valid
        query_keys = ["id", "key"]
        if cycle_keys is not None:
            query_keys.extend(cycle_keys)

        for key in query_keys:
            if key not in test_cycles[0].keys():
                raise KeyError(
                    f"Query parameter {key} is not a queriable parameter in test cycles."
                )

        # Prepare the output
        outputs = []
        for cycle in test_cycles:
            outputs.append({key: cycle[key] for key in query_keys})

        return outputs

    async def get_test_execution(self, test_execution_key):
        """
        Get the details of a test execution.

        Parameters
        ----------
        test_execution_key : str
            The key of the test execution.

        Returns
        -------
        dict
            A dictionary containing the details of the test execution.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Test-Executions/operation/getTestExecution
        """
        endpoint = f"testexecutions/{test_execution_key}"
        url = self.zephyr_base_url + endpoint
        headers = {
            "Authorization": f"Bearer {self.zephyr_api_token}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(url=url, headers=headers) as response:
                values: dict = await response.json()
                self.log.debug(
                    f"Querying test execution {test_execution_key}. Got response: {values=}"
                )
                return values

    async def get_test_execution_steps(self, test_execution_key):
        """
        Get all the steps in a test execution.

        Parameters
        ----------
        test_execution_key : str
            The key of the test execution.

        Returns
        -------
        dict
            A dictionary containing the steps of the test execution.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Test-Executions/operation/getTestExecutionTestSteps
        """
        endpoint = f"testexecutions/{test_execution_key}/teststeps"
        url = self.zephyr_base_url + endpoint
        headers = {
            "Authorization": f"Bearer {self.zephyr_api_token}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(url=url, headers=headers) as response:
                values: dict = await response.json()
                self.log.debug(
                    f"Querying steps in test execution {test_execution_key}. Got response: {values=}"
                )
                return values

    async def get_test_executions(self, test_cycle_key, max_results=20):
        """
        Get all the test executions inside a test cycle.

        Parameters
        ----------
        test_cycle_key : str
            The key of the test cycle.
        max_results : int
            The maximum number of test executions to return.

        Returns
        -------
        dict
            A dict that contains a list of test executions.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Test-Executions/operation/getTestExecutions
        """
        endpoint = "testexecutions"
        url = self.zephyr_base_url + endpoint
        headers = {
            "Authorization": f"Bearer {self.zephyr_api_token}",
            "Content-Type": "application/json",
        }
        query_parameters = {
            "testCycle": test_cycle_key,
            "maxResults": max_results,
        }

        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(
                url=url, headers=headers, params=query_parameters
            ) as response:
                values: list[dict] = await response.json()
                self.log.debug(
                    f"Querying test executions in test cycle {test_cycle_key}. Got response: {values=}"
                )

        return values

    async def get_user_name(self, account_id):
        """
        Get the user name based on a JSON object containing "self"
        and "accountId" keys.

        Parameters
        ----------
        account_id : int
            The account ID of the user.

        Returns
        -------
        str
            The user name.
        """
        endpoint = "user"
        url = self.jira_base_url + endpoint

        if self.jira_api_token is None:
            raise ValueError("JIRA API token is not set")

        query_parameters = {
            "accountId": account_id,
        }

        async with aiohttp.ClientSession(
            auth=BasicAuth(f"{self.jira_username}@lsst.org", self.jira_api_token)
        ) as session:
            async with session.get(url, params=query_parameters) as response:
                response_text = await response.text()
                if response.status == 200:
                    user_details = await response.json()
                    self.log.debug(
                        f"Token is working fine. User display name: {user_details['displayName']}"
                    )
                else:
                    raise aiohttp.ClientError(
                        f"Failed to authenticate. Status code: {response.status} {response_text}"
                    )
        return user_details["displayName"]

    async def get_project(self, project_id):
        """
        Query the project based on a JSON object containing "self" and
        "id" keys.

        Parameters
        ----------
        project_id : int
            And number representing the project ID.

        Returns
        -------
        dict
            A dictionary containing the details of the project.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Projects/operation/getProject
        """
        endpoint = f"projects/{project_id}"
        url = self.zephyr_base_url + endpoint
        headers = {
            "Authorization": f"Bearer {self.zephyr_api_token}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(url, headers=headers) as response:
                project = await response.json()

        return project["key"]

    async def get_status(self, status_id):
        """
        Get the details of a status.

        Parameters
        ----------
        status_id : int
            The ID of the status.

        Returns
        -------
        dict
            A dictionary containing the details of the status.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Statuses/operation/getStatus
        """
        endpoint = f"statuses/{status_id:d}"
        url = self.zephyr_base_url + endpoint
        headers = {
            "Authorization": f"Bearer {self.zephyr_api_token}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(url=url, headers=headers) as response:
                status = await response.json()

        return status["name"]

    async def get_statuses(self, status_type=None, max_results=20):
        """
        Get all the available statuses in Zephyr Scale.

        Returns
        -------
        dict
            A dictionary containing the available statuses.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Statuses/operation/listStatuses
        """
        endpoint = "statuses"
        url = self.zephyr_base_url + endpoint
        headers = {
            "Authorization": f"Bearer {self.zephyr_api_token}",
            "Content-Type": "application/json",
        }

        params = {"maxResults": max_results}
        if status_type in ["TEST_CASE", "TEST_PLAN", "TEST_CYCLE", "TEST_EXECUTION"]:
            params["statusType"] = status_type

        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(url, headers=headers, params=params) as response:
                statuses = await response.json()
        return statuses


async def run_example():

    # Create a ZephyrInterface object
    zephyr_api_token = os.getenv("ZEPHYR_API_TOKEN")
    jira_api_token = os.getenv("JIRA_API_TOKEN")
    jira_username = os.getenv("JIRA_USERNAME")

    zephyr_interface = ZephyrInterface(
        jira_api_token=jira_api_token,
        jira_username=jira_username,
        zephyr_api_token=zephyr_api_token,
    )

    # Retrieve all available statuses
    statuses = await zephyr_interface.get_statuses()
    with open("statuses.json", "w") as file:
        json.dump(statuses, file, indent=4)
    print(f'\nSaved statuses inside "{file.name}"')

    # # Retrieve a test case
    test_case_key = "BLOCK-T21"
    test_case = await zephyr_interface.get_test_case(test_case_key)
    with open(f"{test_case_key}.json", "w") as file:
        json.dump(test_case, file, indent=4)
    print(f"Saved data from {test_case_key} inside {file.name}")

    # # Retrieve steps in a test case
    test_case_steps = await zephyr_interface.get_test_case_steps(test_case_key)
    with open(f"{test_case_key}_steps.json", "w") as file:
        json.dump(test_case_steps, file, indent=4)
    print(f"Saved data from {test_case_key} inside {file.name}")

    # Retrieve a specific test execution
    test_execution_key = "BLOCK-E192"
    test_execution = await zephyr_interface.get_test_execution(test_execution_key)
    with open(f"{test_execution_key}.json", "w") as file:
        json.dump(test_execution, file, indent=4)
    print(f"Saved data from {test_execution_key} inside {file.name}")

    # Retrieve the test case name and version from the test execution
    (
        test_case_name,
        test_case_version,
    ) = zephyr_interface.extract_test_case_from_test_execution(test_execution)
    print(
        f"From {test_execution_key}, Test case name: {test_case_name}, "
        f"Test case version: {test_case_version}\n"
    )

    # Retrieve steps in a test execution
    test_execution_steps = await zephyr_interface.get_test_execution_steps(
        test_execution_key
    )
    with open(f"{test_execution_key}_steps.json", "w") as file:
        json.dump(test_execution_steps, file, indent=4)
    print(f"Saved data from {test_execution_key} inside {file.name}")

    # Retrieve test cycles
    print("Querying many test cycles...")
    test_cycles = await zephyr_interface.get_test_cycles(
        start_at=20, cycle_keys=["name"]
    )
    print("Got them. ")

    for tc in test_cycles:
        print("  ", tc["key"], tc["name"])

    with open("test_cycles.json", "w") as file:
        json.dump(test_cycles, file, indent=4)
        print(f"Saved data from test cycles inside {file.name}\n")

    # Retrieve a test cycle
    test_cycle_key = test_cycles[0]["key"]
    test_cycle = await zephyr_interface.get_test_cycle(test_cycle_key)
    with open(f"{test_cycle_key}.json", "w") as file:
        json.dump(test_cycle, file, indent=4)
    print(f"Saved data from {test_cycle_key} inside {file.name}")

    # Retrieve test executions inside a test cycle
    test_executions = await zephyr_interface.get_test_executions(test_cycle_key)
    with open(f"{test_cycle_key}_executions.json", "w") as file:
        json.dump(test_executions, file, indent=4)
    print(f"Saved data from {test_cycle_key} inside {file.name}")


def run_zephyr_interface():
    asyncio.run(run_example())


if __name__ == "__main__":
    asyncio.run(run_example())
