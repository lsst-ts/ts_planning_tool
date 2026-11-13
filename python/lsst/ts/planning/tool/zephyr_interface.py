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
    "AddTestCasesError",
    "ZephyrInterface",
    "format_zephyr_date",
]

import asyncio
import logging
import re
from datetime import datetime, timezone

import aiohttp
from aiohttp import BasicAuth

# Your JIRA Cloud base URL
ZEPHYR_BASE_URL = "https://api.zephyrscale.smartbear.com/v2/"
JIRA_BASE_URL = "https://rubinobs.atlassian.net/rest/api/2/"

# Headers sent with every request. Jira answers with Brotli-compressed bodies
# when the client accepts them, and aiohttp >= 3.13 fails to decode them with
# Brotli < 1.2 ("process() takes exactly 1 argument"), which some Rubin
# environments still ship. Asking only for gzip/deflate avoids the problem.
SESSION_HEADERS = {"Accept-Encoding": "gzip, deflate"}


def format_zephyr_date(value):
    """
    Format a date the way the Zephyr Scale API expects it.

    Parameters
    ----------
    value : datetime, str or None
        A `datetime` is converted to UTC (a naive one is taken as UTC).
        A string or None is returned unchanged.

    Returns
    -------
    str or None
        e.g. `2026-11-16T03:00:00Z`.
    """
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class AddTestCasesError(RuntimeError):
    """
    Raised when a test execution cannot be added to a test cycle.

    Attributes
    ----------
    test_cycle_key : str
        The test cycle.
    failed_key : str
        The test case that could not be added.
    added : list of dict
        The executions created before the error, which are not undone.
    """

    def __init__(self, test_cycle_key, failed_key, added):
        self.test_cycle_key = test_cycle_key
        self.failed_key = failed_key
        self.added = added
        super().__init__(
            f"Could not add {failed_key} to {test_cycle_key} after adding "
            f"{len(added)} test case(s): {[item['key'] for item in added]}"
        )


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
        https://rubinobs.atlassian.net/plugins/servlet/ac/\
            com.kanoah.test-manager/api-access-tokens

    Then, store the API tokens inside the JIRA_API_TOKEN and ZEPHYR_API_TOKEN
    environment variables, and the email address of your Atlassian account
    in the JIRA_USERNAME environment variable.

    Parameters
    ----------
    jira_api_token : str
        The Jira Cloud API token.
    jira_base_url : str
        The base URL of the Jira REST API.
    jira_username : str
        The email address of the Atlassian account that owns
        `jira_api_token`, e.g. `jdoe@lsst.org`. A value without `@` is taken
        as a bare Rubin username and `@lsst.org` is appended.
    zephyr_api_token : str
        The Zephyr Scale API access token.
    zephyr_base_url : str
        The base URL of the Zephyr Scale API.
    log : logging.Logger
        The logger object to use for logging.
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

    @property
    def jira_login(self):
        """
        The login for Jira Basic auth: the email address of the Atlassian
        account. `jira_username` is used as is when it contains `@`;
        otherwise it is taken as a bare Rubin username and `@lsst.org` is
        appended, as older versions of this package required.
        """
        if self.jira_username is None or "@" in self.jira_username:
            return self.jira_username
        return f"{self.jira_username}@lsst.org"

    async def get(self, endpoint, params=None):
        """
        Generic method to make HTTP GET requests to the Zephyr Scale API and
        return the payload.
        """
        url = self.zephyr_base_url + endpoint
        headers = {
            "Authorization": f"Bearer {self.zephyr_api_token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession(
            raise_for_status=True, headers=SESSION_HEADERS
        ) as session:
            async with session.get(url, headers=headers, params=params) as response:
                payload = await response.json()

        return payload

    async def get_all(self, endpoint, params=None, max_results=100):
        """
        Make as many HTTP GET requests as needed to retrieve every item of a
        paginated Zephyr Scale endpoint.

        Parameters
        ----------
        endpoint : str
            The paginated endpoint, relative to the Zephyr Scale base URL.
        params : dict, optional
            Query parameters. Any `startAt` or `maxResults` in it is ignored.
        max_results : int, optional
            Requested page size. The server may use a smaller one; when this
            happens, the following pages are requested with the page size
            that the server returned.

        Returns
        -------
        list
            The items of all the pages, in the order the server returned them.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #section/Pagination
        """
        params = params or {}
        start_at = 0
        values = []

        while True:
            page_params = params | {"startAt": start_at, "maxResults": max_results}
            page = await self.get(endpoint, page_params)
            values.extend(page["values"])
            self.log.debug(
                f"Got {len(values)} of {page.get('total', '?')} items from {endpoint}"
            )

            # An empty page also stops the loop, in case `isLast` is missing
            # or wrong, so we never request the same page forever.
            if page.get("isLast", True) or not page["values"]:
                break

            # `startAt` must be a multiple of the page size in use.
            max_results = page.get("maxResults") or max_results
            start_at = page.get("startAt", start_at) + max_results

        return values

    async def post(self, endpoint, payload, max_retries=3):
        """
        Generic method to make HTTP POST requests to the Zephyr Scale API and
        return the response payload.

        The API does not document its rate limits, so a `429 Too Many
        Requests` answer is retried after the `Retry-After` delay (or 1, 2,
        4... seconds) up to `max_retries` times.

        Parameters
        ----------
        endpoint : str
            The endpoint, relative to the Zephyr Scale base URL.
        payload : dict
            The JSON body of the request.
        max_retries : int, optional
            How many times to retry after a `429` answer.

        Returns
        -------
        dict
            The JSON body of the response.

        Raises
        ------
        aiohttp.ClientResponseError
            If the API answers with an error. Its message includes the body
            of the answer, where Zephyr Scale explains what was wrong.
        """
        url = self.zephyr_base_url + endpoint
        headers = {
            "Authorization": f"Bearer {self.zephyr_api_token}",
            "Content-Type": "application/json",
        }

        for attempt in range(max_retries + 1):
            async with aiohttp.ClientSession(headers=SESSION_HEADERS) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 429 and attempt < max_retries:
                        try:
                            delay = float(response.headers.get("Retry-After", ""))
                        except ValueError:
                            delay = 2**attempt
                        self.log.warning(
                            f"Rate limited on POST {endpoint}; retrying in {delay} s"
                        )
                        await asyncio.sleep(delay)
                        continue

                    if response.status >= 400:
                        body = await response.text()
                        raise aiohttp.ClientResponseError(
                            response.request_info,
                            response.history,
                            status=response.status,
                            message=f"{response.reason}: {body}",
                            headers=response.headers,
                        )

                    return await response.json()

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

    async def get_steps_from_call_to_test(self, json_steps: list):
        """
        Get the steps from a call to a test case.

        Parameters
        ----------
        json_steps : list
            A list containing the steps of a test case.

        Returns
        -------
        list
            A list containing the steps of the test case.
        """
        steps = []
        for single_step in json_steps:
            if "testCase" in single_step and single_step["testCase"] is not None:
                self.log.info(
                    f"  Parsing sub-steps from test case:"
                    f"  {single_step['testCase']['testCaseKey']}"
                )
                # Call get_steps_in_test_case with call_to_test=False to avoid
                # infinite recursion.
                sub_steps = await self.get_steps_in_test_case(
                    single_step["testCase"]["testCaseKey"], call_to_test=False
                )
                steps.extend(sub_steps["values"])
            else:
                steps.append(single_step)
        return steps

    async def get_steps_in_test_case(self, key, call_to_test=False):
        """
        Get all the steps in a test case.

        Parameters
        ----------
        test_key : str
            The key of the test case or test execution.
        call_to_test : bool
            Merge steps from test cases that are called from the main test
            case.

        Returns
        -------
        dict
            A dictionary containing the steps of the test case.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Test-Cases/operation/getTestCaseTestSteps
        """
        endpoint = f"testcases/{key}/teststeps"
        payload = await self.get(endpoint)

        if call_to_test:
            payload["values"] = await self.get_steps_from_call_to_test(
                payload["values"]
            )

        return payload

    async def get_steps_in_test_execution(self, test_key):
        """
        Get all the steps in a test execution.

        Parameters
        ----------
        test_key : str
            The key of the test case or test execution.

        Returns
        -------
        dict
            A dictionary containing the steps of the test case.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Test-Executions/operation/getTestExecutionTestSteps
        """
        endpoint = f"testexecutions/{test_key}/teststeps"
        payload = await self.get(endpoint)
        return payload

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

        tasks = [
            self.parse(test_case[key], parse=parse) for key, val in parse_fields.items()
        ]
        parsed_fields = await asyncio.gather(*tasks)
        for (key, _), parsed in zip(parse_fields.items(), parsed_fields):
            test_case[key] = parsed

        parse_users = ["owner"]

        for user in parse_users:
            test_case[user] = await self.get_user_name(test_case[user])
            if test_case[user] and parse == "simple":
                test_case[user] = test_case[user]["displayName"]

        if parse == "full":
            test_case["testScript"] = test_case[
                "testScript"
            ] | await self.get_steps_in_test_case(test_case_key, call_to_test=True)

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
        async with aiohttp.ClientSession(
            raise_for_status=True, headers=SESSION_HEADERS
        ) as session:
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

        t_start = datetime.now()
        self.log.info(f"Parsing information for {test_execution_key} - START")
        for key, val in parse_fields.items():
            test_execution[key] = await self.parse(test_execution[key])
            if test_execution[key] and parse == "simple":
                test_execution[key] = test_execution[key][val]

        parse_users = ["executedById", "assignedToId"]

        for user in parse_users:
            test_execution[user] = await self.get_user_name(test_execution[user])
            if test_execution[user] and parse == "simple":
                test_execution[user] = test_execution[user]["displayName"]

        # Fill the payload with the test execution steps
        if parse == "full":
            # Get the test execution and test case steps, they should have the
            # same number of elements (steps).
            # TODO: an execution keeps its own copy of the steps from when it
            # was created, but the test case steps are read as they are now.
            # When the test case was edited afterwards (even without a new
            # version), the counts differ and the assert below fails, e.g.
            # BLOCK-E306 has 5 steps and BLOCK-T21 (still version 1) has 4.
            # The API cannot read the steps of an older version either (its
            # `testScript.self` points to the current steps). Pair the steps
            # some other way, or keep the execution's steps when they differ.
            test_execution_steps = await self.get_steps_in_test_execution(
                test_execution_key
            )
            test_case_steps = await self.get_steps_in_test_case(
                test_execution["testCase"]["key"], call_to_test=True
            )
            assert len(test_execution_steps["values"]) == len(test_case_steps["values"])

            # Loop for each step to merge the information in the json payload
            for exec_step, case_step in zip(
                test_execution_steps["values"], test_case_steps["values"]
            ):
                exec_step["inline"] = exec_step["inline"] | case_step["inline"]

            test_execution["testScript"] = test_execution_steps

        delta_t = datetime.now() - t_start
        self.log.info(
            f"Parsing information for {test_execution_key} in {delta_t} s - DONE"
        )

        return test_execution

    async def list_test_executions(
        self, test_key, max_results=20, only_last=False, parse="raw"
    ):
        """
        Get all the test executions inside a test cycle or corresponding to a
        test case.

        Parameters
        ----------
        test_key : str
            The key of the test cycle or test case.
        max_results : int
            A hint as to the maximum number of results to return in each call.
            Note that the server reserves the right to impose a `max_results`
            limit that is lower than the value that a client provides, due to
            lack or resources or any other condition. When this happens, your
            results will be truncated. Callers should always check the returned
            `max_results` to determine the value that is effectively being
            used.
        only_last: bool, optional
            If True, only the last test execution will be returned. The default
            is `false`.
        parse : string, optional
            The type of parsing to perform. The default is "raw". The other
            options are "full" and "simple". "full" will parse all the fields
            in the test execution and keep existing values. "simple" will strip
            out existing values and only keep the parsed values.

        Returns
        -------
        dict
            A dict that contains a list of test executions.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Test-Executions/operation/getTestExecutions
        """
        if re.search(r"(.+-R[0-9]+)", test_key):
            param_key = "testCycle"
            self.log.info(f"Querying test executions in test cycle {test_key}")
        elif re.search(r"(.+-T[0-9]+)", test_key):
            param_key = "testCase"
            self.log.info(f"Querying test executions in test case {test_key}")
        else:
            raise ValueError("Invalid test key")

        params = {
            param_key: test_key,
            "maxResults": max_results,
            "onlyLastExecutions": str(only_last),
        }
        endpoint = "testexecutions"
        response = await self.get(endpoint, params)

        if parse == "raw":
            return response

        parse_fields = {
            "project": "key",
            "testCase": "key",
            "environment": "name",
            "testExecutionStatus": "name",
            "testCycle": "key",
        }

        parse_users = ["executedById", "assignedToId"]

        self.log.debug(f"Found {len(response['values'])} test executions")
        for test_execution in response["values"]:
            self.log.info(f"Querying test execution {test_execution['key']}")
            for key, val in parse_fields.items():
                test_execution[key] = await self.parse(test_execution[key])
                if test_execution[key] and parse == "simple":
                    test_execution[key] = test_execution[key][val]

            for user in parse_users:
                test_execution[user] = await self.get_user_name(test_execution[user])
                if test_execution[user] and parse == "simple":
                    test_execution[user] = test_execution[user]["displayName"]

        return response

    async def list_test_cases_in_cycle(self, test_cycle_key):
        """
        Get the test cases in a test cycle.

        The test cases come from the test executions of the cycle, so this
        follows every page of results. A test case with more than one
        execution in the cycle is listed once, at the position of its first
        execution.

        Parameters
        ----------
        test_cycle_key : str
            The key of the test cycle, e.g. `BLOCK-R505`.

        Returns
        -------
        list of dict
            One dict per test case, in the order the API returned the test
            executions, with:

            - `key`: the test case key, e.g. `BLOCK-T18`.
            - `version`: the test case version the execution uses (int).
            - `environmentId`: the id of the execution's environment, or None.
              `get_environments` gives the names.

        Notes
        -----
        The API returns the test executions in the order they were created.
        This is not the order shown in the Zephyr Scale UI when the cycle was
        reordered by hand, and the API has no field with the UI order.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Test-Executions/operation/listTestExecutions
        """
        if not re.fullmatch(r".+-R[0-9]+", test_cycle_key):
            raise ValueError(f"Invalid test cycle key: {test_cycle_key}")

        self.log.info(f"Querying test cases in test cycle {test_cycle_key}")
        test_executions = await self.get_all(
            "testexecutions", {"testCycle": test_cycle_key}
        )

        # The test case reference has no key, only a `self` URL like
        # `.../testcases/BLOCK-T18/versions/1`. Reading the key from the URL
        # saves one request per test execution.
        test_cases = []
        seen = set()
        for test_execution in test_executions:
            url = test_execution["testCase"]["self"]
            match = re.search(r"/testcases/([^/]+-T[0-9]+)/versions/([0-9]+)", url)
            if match is None:
                raise ValueError(
                    f"Cannot find the test case key of {test_execution['key']} "
                    f"in {url}"
                )
            if match.group(1) in seen:
                continue
            seen.add(match.group(1))
            environment = test_execution.get("environment")
            test_cases.append(
                {
                    "key": match.group(1),
                    "version": int(match.group(2)),
                    "environmentId": environment["id"] if environment else None,
                }
            )

        return test_cases

    async def get_environments(self, project_key="BLOCK"):
        """
        Get the environments of a project.

        In the Zephyr Scale UI, the test executions of a cycle are shown
        grouped by environment, in the order of the environment `index`.

        Parameters
        ----------
        project_key : str, optional
            The key of the Jira project. The default is "BLOCK".

        Returns
        -------
        list of dict
            The environments, each with `id`, `name`, `description`, `index`
            and `archived`.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Environments/operation/listEnvironments
        """
        return await self.get_all("environments", {"projectKey": project_key})

    async def get_folders(self, project_key="BLOCK", folder_type="TEST_CYCLE"):
        """
        Get the folders of a project.

        Parameters
        ----------
        project_key : str, optional
            The key of the Jira project. The default is "BLOCK".
        folder_type : str, optional
            `TEST_CYCLE` (default), `TEST_CASE` or `TEST_PLAN`.

        Returns
        -------
        list of dict
            The folders, each with `id`, `parentId` (None for root folders),
            `name`, `index`, `folderType` and `project`.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Folders/operation/listFolders
        """
        params = {"projectKey": project_key, "folderType": folder_type}
        return await self.get_all("folders", params)

    async def get_or_create_folder(
        self, path, project_key="BLOCK", folder_type="TEST_CYCLE", dry_run=False
    ):
        """
        Find a folder by its path and create it if it does not exist.

        Only the last folder of the path is created. Its parents must exist,
        so that a typo in the path cannot create a new folder tree.

        Parameters
        ----------
        path : str
            The folder path, e.g. `/LSST Survey Plans/2026/week47`.
        project_key : str, optional
            The key of the Jira project. The default is "BLOCK".
        folder_type : str, optional
            `TEST_CYCLE` (default), `TEST_CASE` or `TEST_PLAN`.
        dry_run : bool, optional
            If True, never create the folder.

        Returns
        -------
        folder_id : int or None
            The id of the folder, or None if it does not exist and `dry_run`
            is True.
        status : str
            `found`, `created`, or `missing` (`dry_run` only).

        Raises
        ------
        ValueError
            If the path is empty, a parent folder does not exist, or more than
            one folder matches.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Folders/operation/createFolder
        """
        names = [name for name in path.split("/") if name.strip()]
        if not names:
            raise ValueError(f"Invalid folder path: {path!r}")

        folders = await self.get_folders(project_key, folder_type)

        parent_id = None
        for depth, name in enumerate(names):
            matches = [
                folder
                for folder in folders
                if folder["name"] == name and folder["parentId"] == parent_id
            ]
            if len(matches) > 1:
                raise ValueError(f"More than one folder matches {path!r} at {name!r}")
            if matches:
                parent_id = matches[0]["id"]
                continue

            if depth < len(names) - 1:
                missing = "/" + "/".join(names[: depth + 1])
                raise ValueError(
                    f"Parent folder {missing!r} does not exist; create it in the "
                    f"Zephyr Scale UI first."
                )
            if dry_run:
                self.log.info(f"Folder {path!r} does not exist (dry run)")
                return None, "missing"

            payload = {
                "parentId": parent_id,
                "name": name,
                "projectKey": project_key,
                "folderType": folder_type,
            }
            response = await self.post("folders", payload)
            self.log.info(f"Created folder {path!r} with id {response['id']}")
            return response["id"], "created"

        return parent_id, "found"

    async def create_test_cycle(
        self,
        name,
        project_key="BLOCK",
        description=None,
        planned_start_date=None,
        planned_end_date=None,
        folder_id=None,
        status_name=None,
        owner_id=None,
    ):
        """
        Create a test cycle.

        Parameters
        ----------
        name : str
            The name of the test cycle.
        project_key : str, optional
            The key of the Jira project. The default is "BLOCK".
        description : str, optional
            The description; HTML is allowed.
        planned_start_date, planned_end_date : datetime or str, optional
            Planned dates. A `datetime` is converted to UTC (a naive one is
            taken as UTC); a string is sent as is, and must look like
            `2026-11-16T03:00:00Z`.
        folder_id : int, optional
            The id of a `TEST_CYCLE` folder.
        status_name : str, optional
            The name of the test cycle status, e.g. `Not Executed`.
        owner_id : str, optional
            The Atlassian account id of the owner.

        Returns
        -------
        dict
            The new test cycle's `id`, `self` and `key`.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Test-Cycles/operation/createTestCycle
        """
        optional = {
            "description": description,
            "plannedStartDate": format_zephyr_date(planned_start_date),
            "plannedEndDate": format_zephyr_date(planned_end_date),
            "folderId": folder_id,
            "statusName": status_name,
            "ownerId": owner_id,
        }
        payload = {"projectKey": project_key, "name": name} | {
            key: value for key, value in optional.items() if value is not None
        }

        response = await self.post("testcycles", payload)
        self.log.info(f"Created test cycle {response.get('key')}: {name!r}")
        return response

    async def add_test_cases_to_cycle(
        self, test_cycle_key, test_cases, status_name="Not Executed"
    ):
        """
        Add test cases to a test cycle, one test execution per test case.

        The executions are created one at a time, in the order given, so the
        order of `test_cases` is the order they are created in.

        Parameters
        ----------
        test_cycle_key : str
            The key of the test cycle, e.g. `BLOCK-R760`.
        test_cases : list of str or dict
            Test case keys, or dicts with `key` and, optionally,
            `environment` (an environment name such as `1. Daytime`).
        status_name : str, optional
            The status of the new executions. The default is `Not Executed`.

        Returns
        -------
        list of dict
            One dict per created execution, with the test case `key`, the
            `environment` and the new execution `id`.

        Raises
        ------
        AddTestCasesError
            If an execution cannot be created. Its `added` attribute lists
            the executions created before the error; they are not undone,
            because the API cannot delete test executions.

        Notes
        -----
        The API has no field to choose the test case version, so the
        executions use the version the API picks, and it documents that
        test cases with "call to test", parameters or test data are not
        supported.

        See also
        --------
        * https://support.smartbear.com/zephyr-scale-cloud/api-docs/\
                #tag/Test-Executions/operation/createTestExecution
        """
        match = re.fullmatch(r"([A-Z][A-Z_0-9]+)-R[0-9]+", test_cycle_key)
        if match is None:
            raise ValueError(f"Invalid test cycle key: {test_cycle_key}")
        project_key = match.group(1)

        added = []
        for test_case in test_cases:
            if isinstance(test_case, str):
                test_case = {"key": test_case}
            payload = {
                "projectKey": project_key,
                "testCycleKey": test_cycle_key,
                "testCaseKey": test_case["key"],
                "statusName": status_name,
                # The API marks executions as automated unless told not to.
                "automated": False,
            }
            if test_case.get("environment"):
                payload["environmentName"] = test_case["environment"]

            try:
                response = await self.post("testexecutions", payload)
            except aiohttp.ClientResponseError as error:
                raise AddTestCasesError(
                    test_cycle_key, test_case["key"], added
                ) from error

            added.append(
                {
                    "key": test_case["key"],
                    "environment": test_case.get("environment"),
                    "id": response["id"],
                }
            )
            self.log.info(f"Added {test_case['key']} to {test_cycle_key}")

        return added

    async def get_myself(self):
        """
        Get the Jira account of the credentials in use.

        Returns
        -------
        dict
            The Jira user, including `accountId` and `displayName`.

        See also
        --------
        * https://developer.atlassian.com/cloud/jira/platform/rest/v2/\
                api-group-myself/#api-rest-api-2-myself-get
        """
        if self.jira_api_token is None:
            raise ValueError("JIRA API token is not set")

        async with aiohttp.ClientSession(
            auth=BasicAuth(self.jira_login, self.jira_api_token),
            raise_for_status=True,
            headers=SESSION_HEADERS,
        ) as session:
            async with session.get(self.jira_base_url + "myself") as response:
                return await response.json()

    async def get_user_name(self, user):
        """
        Get the user name based on a json_obj payload containing `self` and
        `accountId` keys.

        Parameters
        ----------
        user : dict or str
            This can be a dictionary containing the `self` and `accountId` keys
            representing a user or a single string containng the `accountId`.

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
            self.log.warning("Received `user` as None. Returning None.")
            return None

        url = self.jira_base_url + "user"

        if self.jira_api_token is None:
            raise ValueError("JIRA API token is not set")

        json_obj = {"accountId": user} if isinstance(user, str) else user
        query_parameters = {"accountId": json_obj["accountId"]}

        async with aiohttp.ClientSession(
            auth=BasicAuth(self.jira_login, self.jira_api_token),
            raise_for_status=True,
            headers=SESSION_HEADERS,
        ) as session:
            async with session.get(url, params=query_parameters) as response:
                user_details = await response.json()
                self.log.debug(
                    f"Token is working fine. User display name: {user_details['displayName']}"
                )

        return json_obj | user_details

    async def parse(self, json_obj, parse="full"):
        """
        Generic method to parse get requests to the Zephyr Scale API.

        Parameters
        ----------
        json_obj : dict
            The JSON object to parse.
        parse : string, optional
            The type of parsing to perform. The default is "full". The other
            options are "simple" and "full". "full" will parse all the fields
            in the JSON object and keep existing values. "simple" will strip
            out existing values and only keep the parsed values.

        Returns
        -------
        dict or str or None
            If the JSON object is None, the method will return None.
            Otherwise, it will return a dictionary containing the parsed JSON.
        """
        if json_obj is None:
            self.log.warning("Received json_obj as None. Returning None.")
            return None

        if self.zephyr_base_url in json_obj["self"]:
            endpoint = json_obj["self"].replace(self.zephyr_base_url, "")
        else:
            endpoint = json_obj["self"]

        response = await self.get(endpoint)

        if parse == "simple":
            return response
        else:
            return json_obj | response
