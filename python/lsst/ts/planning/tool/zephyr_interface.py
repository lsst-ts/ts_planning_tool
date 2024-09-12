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

    async def get_list_of_statuses(self, status_type=None, max_results=20):
        """
        List all the available statuses in Zephyr Scale.

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
        params = {"maxResults": max_results}

        if status_type in ["TEST_CASE", "TEST_PLAN", "TEST_CYCLE", "TEST_EXECUTION"]:
            params["statusType"] = status_type

        return await self.get(endpoint, params)

    async def get_steps_in_test_case(self, test_case_key):
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

        Note
        ----
        It seems that the json payload from tests steps does not need any
        parsing. The payload is already in a good format.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Test-Cases/operation/getTestCaseTestSteps
        """
        endpoint = f"testcases/{test_case_key}/teststeps"
        self.log.info(f"Querying steps in test case {test_case_key}")
        return await self.get(endpoint)

    async def get_test_case(self, test_case_key, parse="raw"):
        """
        Get the details of a test case.

        Parameters
        ----------
        test_case_key : str
            The key of the test case.
        parse : string, optional
            The type of parsing to perform. The default is "raw", and it will
            return the payload as it is received. The "raw" option saves one
            extra GET query to Zephyr Scale.

            The other options are "full" and "simple". "full" will parse all
            the fields in the test cycle and keep existing values.
            "simple" will strip out existing values and only keep the parsed
            values.

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
        self.log.info(f"Querying test case {test_case_key}, parse = {parse}")
        test_case = await self.get(endpoint)

        if parse == "raw":
            return test_case

        parse_fields = {
            "project": "key",
            "priority": "name",
            "status": "name",
        }

        for key, val in parse_fields.items():
            test_case[key] = await self.parse(test_case[key])
            if test_case[key] and parse == "simple":
                test_case[key] = test_case[key][val]

        parse_users = ["owner"]

        for user in parse_users:
            test_case[user] = await self.get_user_name(test_case[user])
            if test_case[user] and parse == "simple":
                test_case[user] = test_case[user]["displayName"]

        if parse == "full":
            test_case["testScript"] = test_case[
                "testScript"
            ] | await self.get_steps_in_test_case(test_case_key)

        return test_case

    async def get_test_cycle(self, test_cycle_key, parse="raw"):
        """
        Get the details of a test cycle.

        Parameters
        ----------
        test_cycle_key : str
            The key of the test cycle.
        parse : string, optional
            The type of parsing to perform. The default is "raw". The other
            options are "full" and "simple". "full" will parse all the fields
            in the test cycle and keep existing values. "simple" will strip out
            existing values and only keep the parsed values.

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
        self.log.info(f"Querying test cycle {test_cycle_key}, parse = {parse}")
        test_cycle = await self.get(endpoint)

        if parse == "raw":
            return test_cycle

        parse_fields = {
            "project": "key",
            "status": "name",
        }

        for key, val in parse_fields.items():
            test_cycle[key] = await self.parse(test_cycle[key])
            if test_cycle[key] and parse == "simple":
                test_cycle[key] = test_cycle[key][val]

        parse_users = {
            "owner": "displayName",
        }

        for key, val in parse_users.items():
            test_cycle[key] = await self.get_user_name(test_cycle[key])
            if test_cycle[key] and parse == "simple":
                test_cycle[key] = test_cycle[key][val]

        # TODO - Implement parsing test plans

        return test_cycle

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

    async def get_test_execution(self, test_execution_key, parse="raw"):
        """
        Get the details of a test execution.

        Parameters
        ----------
        test_execution_key : str
            The key of the test execution.
        parse : string, optional
            The type of parsing to perform. The default is "raw". The other
            options are "full" and "simple". "full" will parse all the fields
            in the test execution and keep existing values. "simple" will strip
            out existing values and only keep the parsed values.

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
        test_execution = await self.get(endpoint)

        if parse == "raw":
            return test_execution

        parse_fields = {
            "environment": "name",
            "testCase": "key",
            "testCycle": "key",
            "testExecutionStatus": "name",
            "project": "key",
        }

        for key, val in parse_fields.items():
            test_execution[key] = await self.parse(test_execution[key])
            if test_execution[key] and parse == "simple":
                test_execution[key] = test_execution[key][val]

        parse_users = ["executedById", "assignedToId"]

        for user in parse_users:
            test_execution[user] = await self.get_user_name(test_execution[user])
            if test_execution[user] and parse == "simple":
                test_execution[user] = test_execution[user]["displayName"]

        return test_execution

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

    async def get_user_name(self, user):
        """
        Get the a user name based on a json_obj payload containing `self` and
        `accountId` keys.

        Parameters
        ----------
        user : dict or str
            This can be a dictionary containing the `self` and `accountId` keys
            representing a user or  a single string containng the `accountId`.

        Returns
        -------
        dict
            A dictionary containing the original payload plus the `displayName`
            with the user name.

        Note
        ----
        The API is a bit inconsistent. Test cases and test cycles have users
        represented as json objects while test executions have users
        represented as a single string. This method can handle both cases.
        """
        if user is None:
            self.log.warn("Received `user` as None. Returning None.")
            return None

        url = self.jira_base_url + "user"

        if self.jira_api_token is None:
            raise ValueError("JIRA API token is not set")

        json_obj = {"accountId": user} if isinstance(user, str) else user
        query_parameters = {"accountId": json_obj["accountId"]}

        async with aiohttp.ClientSession(
            auth=BasicAuth(f"{self.jira_username}@lsst.org", self.jira_api_token),
            raise_for_status=True,
        ) as session:
            async with session.get(url, params=query_parameters) as response:

                user_details = await response.json()
                self.log.info(
                    f"Token is working fine. User display name: {user_details['displayName']}"
                )

        return json_obj | user_details

    async def parse(self, json_obj):
        """
        Generic method to parse get requests to the Zephyr Scale API.

        Parameters
        ----------
        json_obj : dict
            The JSON object to parse.
        parse_key : str, optional
            The key to parse. The default is None. If not None, the method will
            provide a single value instead of the entire JSON object.

        Returns
        -------
        dict or str or None
            If the JSON object is None, the method will return None.
            Otherwise, it will return a dictionary containing the parsed JSON.
            If parse_key is not None, the method will return a string with the
            value extracted from the JSON response.
        """
        if json_obj is None:
            self.log.warn("Received json_obj as None. Returning None.")
            return None

        if self.zephyr_base_url in json_obj["self"]:
            endpoint = json_obj["self"].replace(self.zephyr_base_url, "")
        else:
            endpoint = json_obj["self"]

        response = await self.get(endpoint)
        return json_obj | response
