# Testing

The rules live in the Tests section of `AGENTS.md`. This file says how they
apply here.

## Running

```bash
./check.sh -t                                   # all tests
./check.sh -c                                   # with coverage
./check.sh -t -- tests/jira/test_search.py      # one module
./check.sh -t -- --lf -x                        # last failed, stop at first
```

## Recorded data

- Tests never call a live Jira. They replay responses stored in the repo.
- Store each real Jira response as a JSON file under `tests/fixtures/`.
  Replay it through `httpx.MockTransport`, using `patch_async_client` in
  `tests/conftest.py`.
- Scrub a recording before committing it. Remove tokens, cookies, email
  addresses, account IDs and customer text. Replace the site URL with
  `https://example.atlassian.net`.
- Recording is a manual step outside the test run, done with
  `python -m tests.fixtures.record --project <KEY>`. It creates and deletes
  its own labelled issues, so run it only against a sandbox project. Ask the
  user before calling a live Jira.
- If a test needs a response that has no recording and you cannot make one,
  stop and ask. Do not invent the response.
- Most existing tests predate this rule and build responses by hand. Do not
  copy that pattern into new tests.

## A test that can fail

- Assert on values taken from the fixture or the input, written as literals.
  Do not recompute the expected value with the code under test or a copy of
  its logic.
- Check that a new test fails when the behaviour it pins is broken.
- Cover error conditions as well as the happy path.

## Module names

- Directories mirror `src/`: `tests/test_tools/`, `tests/jira/`.
- Name the module for the behaviour it pins, such as
  `test_search_pagination.py` or `test_workflow_errors.py`.

## Shared fixtures

- `tests/conftest.py` holds `clean_config`, `mock_config` (one config),
  `two_configs` and `patch_async_client`. Use them; do not redefine them in
  a test module.
- `tests/jira/conftest.py` holds `client` (a `JiraClient` for
  `https://example.atlassian.net`) and `workflow_transitions` for the Jira
  client tests.

## Skips and flakes

- Do not use `skip`, `skipif`, `xfail` or `importorskip`. A missing
  dependency or fixture file must fail the test.
- Treat a flaky test as a top-severity bug. Find the cause, such as shared
  state, ordering or time. Do not add retries or disable the test.

## Conventions

- pytest with `pytest-asyncio` in auto mode: write `async def test_...`.
- Never write to stdout in test code.
