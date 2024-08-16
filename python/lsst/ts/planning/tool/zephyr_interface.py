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
]

import logging

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

    async def get(self, endpoint, params=None):
        """
        Generic method to parse get requests to the Zephyr Scale API.
        """
        url = self.zephyr_base_url + endpoint
        headers = {
            "Authorization": f"Bearer {self.zephyr_api_token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(url, headers=headers, params=params) as response:
                payload = await response.json()

        return payload

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

    async def get_test_case(self, test_case_key, raw=False):
        """
        Get the details of a test case.

        Parameters
        ----------
        test_case_key : str
            The key of the test case.
        raw : bool
            If True, return the raw JSON response.

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
        self.log.debug(f"Querying test case {test_case_key}, raw = {raw}")
        test_case = await self.get(endpoint)

        if not raw:
            test_case["project"] = await self.parse_project_from_id(
                test_case["project"]["id"]
            )
            test_case["priority"] = await self.parse_priority_from_id(
                test_case["priority"]["id"]
            )
            test_case["status"] = await self.parse_status_from_id(
                test_case["status"]["id"]
            )
            test_case["owner"] = await self.get_user_name(
                test_case["owner"]["accountId"]
            )

        return test_case

    async def get_steps_in_test_case(self, test_case_key):
        """
        Get all the steps in a test case.

        Parameters
        ----------
        test_case_key : str
            The key of the test case.
        raw : bool
            If True, return the raw JSON response.

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
        self.log.debug(f"Querying steps in test case {test_case_key}")
        return await self.get(endpoint)

    async def get_test_cycle(self, test_cycle_key, raw=False):
        """
        Get the details of a test cycle.

        Parameters
        ----------
        test_cycle_key : str
            The key of the test cycle.
        raw : bool, optional
            If True, return the raw JSON response. Default is False.

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
        self.log.debug(f"Querying test cycle {test_cycle_key}")
        values = await self.get(endpoint)

        if raw:
            return values

        values["project"] = await self.parse_project_from_id(values["project"]["id"])
        values["status"] = await self.parse_status_from_id(values["status"]["id"])
        values["owner"] = await self.get_user_name(values["owner"]["accountId"])

        return values

    async def get_test_cycles(
        self, cycle_keys=None, max_results=20, start_at=0, project_key="BLOCK"
    ):
        """
            Get all the test cycles.
            Parameters
            ----------
            cycle_keys : list, optional
                A list containing the query parameters.
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

                test_cycles = await response.json()
                # We are only interested in the list of test cycles
                test_cycles = test_cycles["values"]

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
        self.log.debug(f"Querying test execution {test_execution_key}")
        return await self.get(endpoint)

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
        self.log.debug(f"Querying steps in test execution {test_execution_key}")
        return await self.get(endpoint)

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
        params = {
            "testCycle": test_cycle_key,
            "maxResults": max_results,
        }
        return await self.get(endpoint, params)

    async def get_user_name(self, account_id):
        """
        Get the user name based on a JSON object containing "self"
        and "accountId" keys.

        Parameters
        ----------
        account_id : str
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

                user_details = await response.json()
                self.log.info(
                    f"Token is working fine. User display name: {user_details['displayName']}"
                )

        return user_details["displayName"]

    async def parse_environment_from_id(self, environment_id: int) -> str:
        """
        Query the Zephyr Scale database to get the environment name based on
        its ID.

        Parameters
        ----------
        environment_id : int
            The ID of the environment.

        Returns
        -------
        str
            The environment name.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Environments/operation/getEnvironment
        """
        endpoint = f"environments/{environment_id:d}"
        self.log.debug(f"Querying environment {environment_id}")
        environment = await self.get(endpoint)
        return environment["name"]

    async def parse_priority_from_id(self, priority_id: int) -> str:
        """
        Query the Zephyr Scale database to get the priority name based on its
        ID.

        Parameters
        ----------
        priority_id : int
            The ID of the priority.

        Returns
        -------
        str
            The priority name.
        """
        endpoint = f"priorities/{priority_id:d}"
        self.log.debug(f"Querying priority {priority_id}")
        priority = await self.get(endpoint)
        return priority["name"]

    async def parse_project_from_id(self, project_id: int) -> str:
        """
        Query the Jira project key (e.g. BLOCK, OBS, SITCOM) from the Zephyr
        Scale database based the project's ID.

        Parameters
        ----------
        project_id : int
            And number representing the project ID.

        Returns
        -------
        str
            The project key.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Projects/operation/getProject
        """
        endpoint = f"projects/{project_id:d}"
        self.log.debug(f"Querying project {project_id}")
        project = await self.get(endpoint)
        return project["key"]

    async def parse_status_from_id(self, status_id: int) -> str:
        """
        Get the name of a status from the Zephyr Scale database based on its
        ID number.

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
        self.log.debug(f"Querying status {status_id}")
        status = await self.get(endpoint)
        return status["name"]

    async def parse_test_case_from_id(
        self, test_case_id: int, versions: int = 1
    ) -> str:
        """
        Query the Zephyr Scale database to get the test case key based on its
        ID.

        Parameters
        ----------
        test_case_id : int
            The ID of the test case.

        Returns
        -------
        str
            The test case key.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Test-Cases/operation/getTestCase
        """
        endpoint = f"testcases/{test_case_id:d}/versions/{versions:d}"
        self.log.debug(f"Querying test case {test_case_id}")
        return await self.get(endpoint)["key"]
        raise NotImplementedError(
            "ZephyrScale does not suport parsing Test Cases from ID"
        )
        # endpoint = f"testcases/{test_case_id:d}/versions/{versions:d}"
        # url = self.zephyr_base_url + endpoint
        # headers = {
        #     "Authorization": f"Bearer {self.zephyr_api_token}",
        #     "Content-Type": "application/json",
        # }
        # async with aiohttp.ClientSession(raise_for_status=True) as session:
        #     async with session.get(url, headers=headers) as response:
        #         test_case = await response.json()

        # return test_case["key"]

    async def parse_test_cycle_from_id(self, test_cycle_id: int) -> str:
        """
        Query the Zephyr Scale database to get the test cycle key based on its
        ID.

        Parameters
        ----------
        test_cycle_id : int
            The ID of the test cycle.

        Returns
        -------
        str
            The test cycle key.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Test-Cycles/operation/getTestCycle
        """
        endpoint = f"testcycles/{test_cycle_id:d}"
        self.log.debug(f"Querying test cycle {test_cycle_id}")
        return await self.get(endpoint)["key"]
