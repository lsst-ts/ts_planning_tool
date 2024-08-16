# ts_planning_tool

This package provides tools to be used by LOVE as part of the LOVE Player dashboard.
LOVE Player is an user interface inside LOVE that mimics the Zephyr Scale Test Player, with potential to add extra funcionality.
Since LOVE Player lives inside LOVE, it can interact with the Script Queue to add/remove SAL scripts. 
At the same time, it can potentially save information in Zephyr Scale and send messages to the Observatory Logging Environment (OLE).

To accomplish that, this package provides the following tools:
* Zephyr Scale API 

See each section below. 


## Zephyr Scale API

This module provides a class to interact with [Zephyr Scale API](https://support.smartbear.com/zephyr-scale-cloud/api-docs/). 
It has been tested with Jira Cloud and Zephyr Scale Cloud.
You will need an API token from both for it to work. 
These tokens should be passed directly to the `ZephyrInterface` class, together with the URLs for both Jira and Zephyr Scale.
By default, the URLs are the ones used by Rubin Observatory. 

This module contains unit tests inside `tests` folder. 
Tests with the `_noci` suffix are not supposed to be run in CI pipelines.
Those are used to confirm the API is working as expected using real data. 
You can use them by setting the environment variables:
* `ZEPHYR_API_TOKEN`, 
* `JIRA_API_TOKEN`, 
* `JIRA_USERNAME`

Other unit tests use mock data and can be run in CI pipelines.
The `tests/data` folder contains examples of payloads returned by the API.
Those are used in unit tests to mock the API responses.
