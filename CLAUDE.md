# CLAUDE.md

Context for AI agents and developers working on `ts_planning_tool`.
User-facing documentation (setup, credentials, CLI examples) is in [README.md](README.md); read it too.

## What this is

An async Python client (`ZephyrInterface`) and CLI (`zapi`) for the **Zephyr Scale Cloud API** (test management plug-in for Jira), plus the Jira Cloud `user` endpoint.
It is the backend for **LOVE Player**, a dashboard in LOVE (the Rubin Observatory control UI) that mimics the Zephyr Scale Test Player and can drive the Script Queue.
Long-term goals: write results back to Zephyr Scale and post to OLE (Observatory Logging Environment).

- Zephyr Scale API docs: https://support.smartbear.com/zephyr-scale-cloud/api-docs/
- Jira project: `BLOCK`. Key formats: test case `BLOCK-T21`, test cycle `BLOCK-R21`, test execution `BLOCK-E192`, test plan `BLOCK-P…`.
- Key prefixes are used for dispatch via regex (`-T`, `-R`, `-E`) in `list_test_executions` and in the CLI `get steps` command.

## Layout

```
python/lsst/ts/planning/tool/
  zephyr_interface.py   # ZephyrInterface: all HTTP logic (aiohttp)
  cli.py                # zapi CLI (argparse); entry point run_zapi_command_line
  utils.py              # load_json_data(filename, path) -> reads <path>/data/<filename>
  cycle_order.py        # pure functions: order template cases, place requested cases
  data/cycle_templates.json  # UI order of the template cycles (API can't give it)
  __init__.py           # star-imports the modules above (and version.py, generated)
tests/
  test_zephyr_interface.py         # mocked, runs in CI
  test_zephyr_interface_no_ci.py   # hits real APIs; skipped without env vars
  test_jira_api_no_ci.py           # hits real Jira API; skipped without env vars
  data/*.json                      # recorded API payloads used as mocks
doc/news/               # towncrier news fragments (one per change, per ticket)
conda/meta.yaml, Jenkinsfile*, ups/, SConstruct   # Rubin build/packaging (conda + EUPS)
```

Every new module must define `__all__` and be star-imported in `__init__.py`.

## ZephyrInterface design

- **All network methods are `async`.** Each request opens its own `aiohttp.ClientSession(raise_for_status=True)`; HTTP errors raise `aiohttp.ClientResponseError`.
- `get(endpoint, params)` is the generic Zephyr GET (Bearer token). New read endpoints should go through it.
  Exception: `get_test_cycles` builds its own session (legacy duplication).
- `get_user_name(user)` uses Jira Basic auth with the `jira_login` property: `JIRA_USERNAME` is the full email of the Atlassian account (it is not always `@lsst.org`); a value without `@` gets `@lsst.org` appended for older setups. Accepts an `accountId` string (test executions) or a `{"accountId", "self"}` dict (test cases and cycles).
- `parse(json_obj, parse)` follows a reference's `self` URL and returns the resolved object (`simple`) or the reference merged with it (`full`).
- **Parse modes** on `get_test_case`, `get_test_cycle`, `get_test_execution`, `list_test_executions`:
  - `raw`: payload untouched (no extra requests).
  - `simple`: each reference replaced by a scalar (e.g. `status` → `"Pass"`, users → display name).
  - `full`: references merged with resolved objects; test case / execution also get steps in `testScript`.
- **Steps**:
  - `get_steps_in_test_case(key, call_to_test=True)` expands steps that call another test case (one level only; nested calls are not expanded, which avoids infinite recursion).
  - `get_test_execution(..., parse="full")` zips execution steps with the expanded test-case steps and merges their `inline` dicts; it `assert`s that both have the same number of steps.
- Defaults: `ZEPHYR_BASE_URL = https://api.zephyrscale.smartbear.com/v2/`, `JIRA_BASE_URL = https://rubinobs.atlassian.net/rest/api/2/`.

## Not implemented yet / known issues

- **Test Plans**: no methods; `get_test_cycle` has a `TODO` for parsing linked test plans.
- `get_test_execution(parse="full")` merges the execution's steps with the steps of the **latest** test case version, not the version the execution ran; when the step count changed, its `assert` fails (e.g. `BLOCK-E306`). `test_get_test_execution_full_parse` is marked `xfail` until this is fixed (TODO in the code).
- **No write operations** (no POST/PUT): creating test executions or updating step/execution status is not implemented, even though the class docstring says otherwise.
- **No pagination** beyond a single page (`maxResults`) in `list_test_executions` / `get_test_cycles`.
- `get_test_case(parse="simple")` passes `parse` through to `self.parse()`, so its fields end up as whole resolved objects instead of scalars. This differs from cycle and execution.
- CLI: `zapi list test_executions -m/--max` is ignored. argparse stores it as `max`, but the handler expects `max_results`, so it always uses 5.
- CLI: `setup_logging()` adds a new handler on every call; there is a TODO about log levels not changing as expected.
- `parse` and `get_user_name` requests run sequentially in `simple`/`full` mode (except `get_test_case`, which uses `asyncio.gather`), so large lists are slow.

## Testing

- Mocked tests patch `aiohttp.ClientSession.get` and feed it JSON from `tests/data/`:
  ```python
  mock_response = MagicMock()
  mock_response.json = AsyncMock(return_value=load_json_data("test_case.json"))
  mock_get.return_value.__aenter__.return_value = mock_response
  ```
  Use `side_effect` with a list when a method makes several requests (parse modes do).
  New features need a mocked test plus a recorded payload in `tests/data/`.
  Strip personal data (names, emails, account IDs) from recorded payloads.
- `_no_ci` tests are integration tests against real Rubin data, gated by `@pytest.mark.skipif` on the three env vars.
- `pyproject.toml` sets `asyncio_mode = "auto"`; tests use `unittest.IsolatedAsyncioTestCase`.
- Running: the official route is the `lsstts/develop-env` Docker image + `setup -r .` + `pytest`.
  Outside Docker, a virtualenv with `pip install -e . pytest pytest-asyncio aiohttp` usually works for the mocked tests.

## Conventions

- **Branches/PRs**: branch from `develop`, PR into `develop`; name branches `tickets/DM-XXXXX` after the Jira ticket. `main` is for releases only. Don't commit directly to `main` or `develop`.
- **News fragment required** for every PR: `doc/news/<TICKET>.<type>.rst`, where type ∈ `feature|bugfix|perf|doc|removal|misc`; use `.1`, `.2` suffixes for multiple fragments of the same type.
- **Style**: black, flake8, isort (pre-commit config generated by `ts_pre_commit_conf`; `generate_pre_commit_conf`). NumPy-style docstrings with a `See also` link to the relevant Zephyr API operation. GPL license header at the top of every source file (copy from an existing file).
- Target Python 3.11+ (code relies on `dict | dict` merges). Runtime dependency: `aiohttp` only. If you add one, add it to `conda/meta.yaml` too.
- CLI handlers are `async def name(<positional>, ..., **kwargs)`. argparse `dest` names must match the handler's parameter names because `args.func(**vars(args))` passes them all through.

## Repository state (update as it changes)

As of 2026-11-13:
- Stacked PRs from splitting old PR #5 (DM-44804) are open: **#8** (utility module → `develop`), **#9** (ZephyrInterface steps/full parse → #8), **#10** (CLI unified `get steps` → #9).
  After each merges, retarget the next PR's base to `develop`.
- PR **#7** (`main` → `develop`, version history) and PR **#11** (`update_readme`, token setup docs, now folded into README here) are open.
- Untracked files in the repo root (`BLOCK-*.json` payload dumps, a PDF, `build/`, `python/.../schemas/`) are local scratch; don't commit them unless asked.
