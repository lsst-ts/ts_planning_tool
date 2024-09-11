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
You will need API tokens from both for it to work.
Here are the list of environment variables required:
* `ZEPHYR_API_TOKEN`,
* `JIRA_API_TOKEN`,
* `JIRA_USERNAME`

These tokens should be passed directly to the `ZephyrInterface` class, together with the URLs for both Jira and Zephyr Scale.
By default, the URLs are the ones used by Rubin Observatory.


### Unit Tests

This module contains unit tests inside `tests` folder.
Tests with the `_noci` suffix are not supposed to be run in CI pipelines.
Those are used to confirm the API is working as expected using real data.
They are only run if you have the environment variables listed above defined in your working environment.

If you want to run unit tests locally, you will need to run a [lsstts/develop-env](https://hub.docker.com/r/lsstts/develop-env) docker container.
Once inside the container, run the following commands:

```
$ source ~/.setup_dev.py  # Basic setup inside the docker container
$ cd develop/.../ts_planning_tool  # access the repo folder
$ setup -r .  # install the package using EUPS
```

Then you can run unit tests by simply executing:

```
$ pytest
```

Other unit tests use mock data and can be run in CI pipelines.
The `tests/data` folder contains examples of payloads returned by the API.
Those are used in unit tests to mock the API responses.


### Command Line Interface (CLI)

This package includes a Zephyr API Command Line Interface (ZAPI CLI).
This is specially useful for exploring the use of this API and to check payloads.
To run it, you will have to follow the steps above *and* install the package using PIP:

```
$ cd ${path_to_the_repo}/ts_planning_tool
$ pip install .
```

After that, check if the command line is working properly in a terminal:

```
$ zapi --help
```

If this script is correctly installed, you should see a short help message.
Use the help in the terminal to navigate further.
