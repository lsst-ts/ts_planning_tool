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
"""Utility functions for the Zephyr Scale API."""

__all__ = ["load_json_data"]

import json
import os


def load_json_data(filename: str, path: str) -> dict:
    """
    Load JSON data from a file.

    Parameters
    ----------
    filename : str
        The name of the file to load.
    path : str
        The path to the file.

    Returns
    -------
    dict
        The JSON data.
    """
    filepath = os.path.join(path, "data", filename)
    with open(filepath, "r") as file:
        return json.load(file)
