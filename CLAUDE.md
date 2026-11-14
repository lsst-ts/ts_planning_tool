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
  weekly_draft.py       # draft_week(zapi, plan, dry_run): checks everything, then writes
  data/cycle_templates.json  # UI order + environment of each template case (API cannot give the order)
  __init__.py           # star-imports the modules above (and version.py, generated)
.claude/skills/draft-weekly-test-cycles/
  SKILL.md              # reading rules: Confluence notes page -> plan JSON -> zapi draft week
  confluence_page.py    # read-only Confluence helper (stdlib; same Atlassian token)
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

- **All network methods are `async`.** Each request opens its own `aiohttp.ClientSession`; HTTP errors raise `aiohttp.ClientResponseError`.
  Every session sends `SESSION_HEADERS` (`Accept-Encoding: gzip, deflate`): Jira's Brotli bodies break aiohttp 3.13 with Brotli < 1.2, which Rubin envs ship.
- `get(endpoint, params)` is the generic Zephyr GET (Bearer token). New read endpoints should go through it.
  Exception: `get_test_cycles` builds its own session (legacy duplication).
- `get_all(endpoint, params)` follows `startAt`/`maxResults` until `isLast` and returns the items as one list. Use it for every list endpoint in new code (the server caps a page at 1000).
- `post(endpoint, payload)` / `put(endpoint, payload)` are the generic writes. They retry `429` (rate limits are undocumented) and put Zephyr's error body in the exception message.
  **A Zephyr PUT replaces the whole entity** (omitted fields are cleared): read it, change one field, send it all back, as `set_test_cycle_status` does.
- **The UI lists a cycle's executions in creation order** (checked on `BLOCK-R755`); environments do not regroup them, so create executions in their final order.
- **Writes** (RSO-1214): `create_test_cycle`, `add_test_cases_to_cycle` (one `POST /testexecutions` per case, sequential, `automated: False`; raises `AddTestCasesError` with what was already added), `get_or_create_folder(path)` (creates only the last folder of the path). The public API **cannot delete test cycles, executions or folders**, so every write is permanent; test real writes in `/LSST Survey Plans/2026/sandbox` and set the cycle to `Cancelled` afterwards.
- **Test case versions cannot be chosen** through the API: neither `POST` nor `PUT /testexecutions` has a version field, and `GET /testcases/{key}/versions/{n}` returns a `testScript` that points to the current steps. The docs also say cases with "call to test" are not supported, but in practice `BLOCK-T250` (calls `BLOCK-T652`) was added fine and its execution got the called steps.
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
- `get_test_execution(parse="full")` merges the execution's steps (a copy made when the execution was created) with the test case's **current** steps. If the test case was edited afterwards, even without a new version, the counts differ and its `assert` fails (e.g. `BLOCK-E306` has 5 steps, `BLOCK-T21` v1 now has 4). The API cannot read an old version's steps. `test_get_test_execution_full_parse` is marked `xfail` until this is fixed (TODO in the code).
- Updating step or execution status is not implemented (only `set_test_cycle_status`), even though the class docstring says otherwise.
- **No pagination** beyond a single page (`maxResults`) in `list_test_executions` / `get_test_cycles` / `get_steps_in_test_case`. The last one matters: the steps endpoint defaults to 10 per page and several cases have more (`BLOCK-T196` 14, `BLOCK-T244` 18), so `parse="full"` silently drops steps.
- `get_test_case(parse="simple")` passes `parse` through to `self.parse()`, so its fields end up as whole resolved objects instead of scalars. This differs from cycle and execution.
- CLI: `zapi list test_executions -m/--max` is ignored. argparse stores it as `max`, but the handler expects `max_results`, so it always uses 5.
- CLI: `setup_logging()` adds a new handler on every call; there is a TODO about log levels not changing as expected.
- `parse` and `get_user_name` requests run sequentially in `simple`/`full` mode (except `get_test_case`, which uses `asyncio.gather`), so large lists are slow.

## TODO: post-merge code review (DM-44804 + RSO-1214)

PR #12 merged a large amount of code into `develop` without a detailed review: the DM-44804 work (planned as the separate PRs #8–#10, closed unreviewed) and RSO-1214 on top of it.
That was accepted to unblock the weekly drafting, but **the code still needs a proper review**. When there is time, review it as if it were a new PR and turn the findings into tickets. Suggested order:

1. **DM-44804** (commits `07e844f`, `ec534d0`, `864b160`): `utils.load_json_data`; steps and `parse="full"` in `ZephyrInterface` (`get_steps_in_test_case`, `get_steps_from_call_to_test`, `get_test_execution`); the `zapi get steps` CLI. Known problems already listed above: the full-parse step mismatch (`xfail`), steps read from one page only, `get_test_case(parse="simple")`, the ignored `--max` flag, sequential parsing.
2. **RSO-1214 write path** (`post`/`put`/`_write`, `create_test_cycle`, `add_test_cases_to_cycle`, `set_test_cycle_status`, `get_or_create_folder`): error handling, retries, and that nothing writes in a dry run.
3. **Drafting** (`cycle_order.py`, `weekly_draft.py`, CLI `draft week` / `add test_cases`) and the skill (`.claude/skills/draft-weekly-test-cycles/`, including the Confluence write in `link_cycles.py`).
4. General: consistency between old and new methods (e.g. `get_test_cycles` vs `get_all`), docstrings, test coverage, black/flake8 with the repository's pre-commit config.

Remove this section once the review is done.

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
- PR **#12** (`tickets/RSO-1214` → `develop`) holds both the DM-44804 work (steps, full parse, `get steps` CLI) and RSO-1214 (weekly test-cycle drafting). It superseded the stacked PRs #8, #9 and #10, which are closed.
- PR **#7** (`main` → `develop`, version history) and PR **#11** (`update_readme`, token setup docs, now folded into README here) are open. If #11 merges first, expect a README conflict in #12.
- Untracked files in the repo root (`BLOCK-*.json` payload dumps, a PDF, `build/`, `python/.../schemas/`, `PLAN_RSO-1214.md`, `HANDOFF_*.md`) are local scratch; don't commit them unless asked.
- Local RSO-1214 notes are in `PLAN_RSO-1214.md`. Throwaway write tests go in `/LSST Survey Plans/2026/sandbox` (`BLOCK-R755`, cancelled).
