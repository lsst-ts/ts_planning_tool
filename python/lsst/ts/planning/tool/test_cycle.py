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

import aiohttp


class TestCycle:
    """
    Direct interface to the Zephyr Scale API for test cycle management.

    Parameters
    ----------
    zapi : ZephyrInterface
        An instance of the ZephyrInterface class.
    """

    def __init__(self, zapi):
        self.zapi = zapi

    async def get_list_of_cycles(
        self, extra_keys=None, max_results=20, start_at=0, project_key="BLOCK"
    ):
        """
        Get a list of test cycles where each test cycle is represented by a
        dictionary containing the test cycle `id` and `key`. `id` is an integer
        containing an unique identifier for the test cycle, and `key` is a
        string with the `{PROJECT_KEY}-R{CYCLE_NUMBER}`.
        For example: BLOCK-R17.

        If `extra_keys` is provided, the dictionary will also contain the
        additional keys specified in the list.

        Parameters
        ----------
        extra_keys : dict, optional
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
        url = self.zapi.zephyr_base_url + endpoint
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
        if extra_keys is not None:
            query_keys.extend(extra_keys)

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
