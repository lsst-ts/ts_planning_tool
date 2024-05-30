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

import unittest
from unittest.mock import MagicMock, patch

from lsst.ts.planning.tool.zephyr.zephyr_interface import ZephyrInterface


class TestZephyrInterface(unittest.TestCase):
    def setUp(self):
        self.username = "test_user"
        self.api_token = "test_token"
        self.zephyr_interface = ZephyrInterface(self.username, self.api_token)

    def test_init(self):
        self.assertEqual(self.zephyr_interface.username, self.username)
        self.assertEqual(self.zephyr_interface.api_token, self.api_token)

    @patch("aiohttp.ClientSession.get")
    async def test_extract_test_case_from_test_execution(self, mock_get):
        test_execution_json = {"key": "TEST-123", "status": "PASS"}
        mock_response = MagicMock()
        mock_response.json.return_value = test_execution_json
        mock_get.return_value.__aenter__.return_value = mock_response

        test_case = await self.zephyr_interface.extract_test_case_from_test_execution(
            test_execution_json
        )
        self.assertEqual(test_case, test_execution_json["key"])

    @patch("aiohttp.ClientSession.get")
    async def test_get_test_case(self, mock_get):
        test_case_key = "TEST-123"
        test_case_json = {"key": test_case_key, "summary": "Test Case Summary"}
        mock_response = MagicMock()
        mock_response.json.return_value = test_case_json
        mock_get.return_value.__aenter__.return_value = mock_response

        test_case = await self.zephyr_interface.get_test_case(test_case_key)
        self.assertEqual(test_case, test_case_json)

    # Add more test methods for other functions in ZephyrInterface class


if __name__ == "__main__":
    unittest.main()
