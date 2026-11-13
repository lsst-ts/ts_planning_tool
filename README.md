# ts_planning_tool

This package provides tools used by LOVE as part of the LOVE Player dashboard.
LOVE Player is a user interface inside LOVE that mimics the Zephyr Scale Test Player, with the potential to add extra functionality.
Since LOVE Player lives inside LOVE, it can interact with the Script Queue to add/remove SAL scripts.
At the same time, it can potentially save information in Zephyr Scale and send messages to the Observatory Logging Environment (OLE).

To accomplish that, this package provides:

* `ZephyrInterface`: an async Python client for the [Zephyr Scale Cloud API](https://support.smartbear.com/zephyr-scale-cloud/api-docs/) (plus the Jira Cloud user endpoint).
* `zapi`: a command line interface built on top of `ZephyrInterface`.


## Zephyr Scale concepts

Zephyr Scale is a Jira plug-in for test management.
At Rubin Observatory it lives in the `BLOCK` Jira project, and object keys follow this pattern:

| Object         | Key example  | Description                                                     |
|----------------|--------------|-----------------------------------------------------------------|
| Test Case      | `BLOCK-T21`  | A reusable procedure made of steps. A step may call another test case. |
| Test Cycle     | `BLOCK-R21`  | A group of test executions.                                     |
| Test Execution | `BLOCK-E192` | One run of a test case, with a status per step.                 |
| Test Plan      | `BLOCK-P…`   | A group of test cycles. *Not supported yet.*                    |

The client tells test cases and test cycles apart by the letter after the project key (`-T` or `-R`), so keep these key formats when calling it.


## Configuration

`ZephyrInterface` needs credentials for both Zephyr Scale and Jira Cloud.
The CLI and the integration tests read them from these environment variables:

| Variable           | Description                                                                 |
|--------------------|-----------------------------------------------------------------------------|
| `ZEPHYR_API_TOKEN` | Zephyr Scale API access token (see below).                                  |
| `JIRA_API_TOKEN`   | Jira Cloud API token, created at <https://id.atlassian.com/manage-profile/security/api-tokens>. |
| `JIRA_USERNAME`    | Your Jira username **without** the `@lsst.org` domain (e.g. `jdoe`). The domain is appended automatically. |

When using the Python class directly, pass these values to the `ZephyrInterface` constructor.
By default, the Jira and Zephyr Scale URLs are the ones used by Rubin Observatory; you can override them with the `jira_base_url` and `zephyr_base_url` arguments.


### Getting your Zephyr Scale API Token

To generate your `ZEPHYR_API_TOKEN`:

1. In Jira, click on your profile at the top right corner. A small window opens showing
   **Profile**, **Account settings**, **Team**, **Slack**, **Assigned items**,
   and **Zephyr Scale API access tokens**.
2. Click on **Zephyr Scale API access tokens**. This takes you to a new page.
3. Click on **Create access token**. This generates a new token, shown as a long string.
4. Copy the token (it is copied to your clipboard) and close the dialog.

The token is valid for one year by default.


### Setting the Environment Variables

A convenient way to define the required environment variables is to keep them in a
separate file that you source from your shell configuration. For example, create a
file called `~/.zapi`:

```zsh
# ts_planning_tool / Zephyr Scale API credentials
export ZEPHYR_API_TOKEN="paste-your-zephyr-token-here"
export JIRA_API_TOKEN="paste-your-jira-token-here"
export JIRA_USERNAME="jdoe"  # without @lsst.org
```

Restrict its permissions so only you can read it, since it holds secrets:

```zsh
chmod 600 ~/.zapi
```

Then source it from your `~/.zshrc` so it loads in every new terminal:

```zsh
[ -f ~/.zapi ] && source ~/.zapi
```

Keep this file private and never commit it to a repository.


## Python Usage

All the request methods are coroutines:

```python
import asyncio
import os

from lsst.ts.planning.tool import ZephyrInterface


async def main():
    zapi = ZephyrInterface(
        zephyr_api_token=os.environ["ZEPHYR_API_TOKEN"],
        jira_api_token=os.environ["JIRA_API_TOKEN"],
        jira_username=os.environ["JIRA_USERNAME"],
    )
    test_case = await zapi.get_test_case("BLOCK-T21", parse="simple")
    executions = await zapi.list_test_executions("BLOCK-R21", only_last=True)


asyncio.run(main())
```

Main methods:

| Method                                   | Returns                                                          |
|------------------------------------------|------------------------------------------------------------------|
| `get_test_case(key, parse)`              | One test case.                                                   |
| `get_test_cycle(key, parse)`             | One test cycle.                                                  |
| `get_test_cycles(cycle_keys, ...)`       | A paginated list of test cycles, reduced to the requested fields. |
| `get_test_execution(key, parse)`         | One test execution.                                              |
| `list_test_executions(key, ...)`         | Test executions of a test case (`-T`) or a test cycle (`-R`).    |
| `get_steps_in_test_case(key, call_to_test)` | Steps of a test case, optionally expanding steps that call other test cases. |
| `get_steps_in_test_execution(key)`       | Steps of a test execution, with their status and results.        |
| `get_list_of_statuses(status_type)`      | Statuses available in Zephyr Scale.                              |
| `get_user_name(user)`                    | Jira display name for an account ID.                             |


### Parse modes

Zephyr Scale returns linked objects (project, status, environment, users, …) as references, e.g. `{"id": 123, "self": "https://..."}`.
The `parse` argument controls whether the client resolves them with extra requests:

* `raw` (default): the payload exactly as returned by Zephyr Scale. Fastest; no extra requests.
* `simple`: resolves references and replaces each one with a single readable value (e.g. the status name or the user's display name).
* `full`: resolves references and merges the full referenced object into each field. For test cases and test executions, it also adds the steps under `testScript`, expanding steps that call other test cases.

`simple` and `full` make one extra request per reference, so they are noticeably slower on large lists.


## Command Line Interface (CLI)

This package includes the Zephyr API Command Line Interface (`zapi`).
It is especially useful for exploring the API and inspecting payloads.
Install it with pip (in addition to the setup in [Unit Tests](#unit-tests) if you are using the development container):

```
$ cd ${path_to_the_repo}/ts_planning_tool
$ pip install .
```

After that, check that it works:

```
$ zapi --help
```

Examples:

```
$ zapi get test_case BLOCK-T21 --parse simple
$ zapi get test_cycle BLOCK-R21 --parse full
$ zapi get test_execution BLOCK-E192 --parse full
$ zapi get steps BLOCK-T21          # steps of a test case (called test cases expanded)
$ zapi get steps BLOCK-E192         # steps of a test execution
$ zapi get user <jira-account-id>
$ zapi list test_executions BLOCK-R21 --only-last --parse simple
```

All commands print JSON to stdout, so you can pipe them to `jq` or redirect them to a file.


## Unit Tests

The unit tests live in the `tests` folder and come in two kinds:

* **Mocked tests** (e.g. `test_zephyr_interface.py`) replace HTTP calls with the example payloads stored in `tests/data`.
  They need no credentials and run in CI.
* **Integration tests** (files ending in `_no_ci.py`) query the real Jira and Zephyr Scale APIs.
  They are not run in CI and are skipped automatically unless the environment variables listed in [Configuration](#configuration) are defined.

To run the tests locally, use a [lsstts/develop-env](https://hub.docker.com/r/lsstts/develop-env) Docker container.
Once inside the container, run:

```
$ source ~/.setup_dev.sh  # Basic setup inside the docker container
$ cd develop/.../ts_planning_tool  # access the repo folder
$ setup -r .  # set up the package using EUPS
```

Then run:

```
$ pytest
```


## Contributing

* Branch from `develop` and open pull requests against `develop`; `main` only receives releases.
  Name branches after the Jira ticket, e.g. `tickets/DM-12345`.
* Add a news fragment for each change in `doc/news/` (see [doc/news/README.rst](doc/news/README.rst)), e.g. `doc/news/DM-12345.feature.rst`.
* Code style is enforced with pre-commit hooks generated by [ts_pre_commit_conf](https://github.com/lsst-ts/ts_pre_commit_conf) (black, flake8, isort, towncrier).
  Run `generate_pre_commit_conf` once in the repo to create the local configuration.
