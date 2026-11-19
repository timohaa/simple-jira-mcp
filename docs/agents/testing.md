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
- `tests/fixtures/<scenario>.json` holds the HTTP exchanges of one client
  operation against a real Jira site. Replay one with the `replay` fixture:
  `jira = replay("search")`. It fails the test if the client sends a request
  the recording does not contain.
- Add or refresh recordings with
  `python -m tests.fixtures.record --project <KEY> [--config-id <ID>]`. It
  reads configs from `JIRA_CONFIG_JSON` and uses the first one unless you
  pass `--config-id`. It creates and deletes its own labelled issues, so run
  it only against a sandbox project. Ask the user before calling a live Jira.
- The recorder scrubs the site, project key, issue keys and user identities.
  Board, sprint, status and priority names stay as recorded, so read every
  new file before committing it. Re-recording changes IDs and timestamps, so
  update the tests that assert on them.
- Scrubbed recordings use fixed placeholders, so assert on these:
  - Site: `https://example.atlassian.net`.
  - Project key: `ONE`. The project name is `Project One`.
  - Issue keys: `ONE-1`, `ONE-2` and so on, numbered in order of first
    appearance across the run. Keys with more than six digits stay as
    recorded.
  - Email: `user@example.com`.
  - Account IDs: `account-1`, `account-2` and so on.
  - Display names: `User 1`, `User 2` and so on.
  - Links to other hosts: `https://media.example.net/file`.
  - Removed fields: `avatarUrls`, `emailAddress` and `timeZone`.
- Record with the account language set to English, so names and error
  messages come back in English.

## What may stay hand-built

- A failure the site cannot produce on demand: a bare status such as 401,
  429 or 500, a malformed body, or a transport error. Pass it to `replay`
  as a fault, or return it from a `httpx.MockTransport` handler.
- A Jira feature the sandbox lacks, such as a transition screen. Say so in
  the test's docstring.
- Return values of our own `JiraClient` methods, mocked in tool tests.
- Anything else needs a recording. If you cannot make one, stop and ask.

## A test that can fail

- Assert on values taken from the fixture or the input, written as literals.
  Do not recompute the expected value with the code under test or a copy of
  its logic.
- Check that a new test fails when the behaviour it pins is broken.

## Module names

- Directories mirror `src/`: `tests/test_tools/`, `tests/jira/`.
- Name the module for the behaviour it pins, such as
  `test_search_pagination.py` or `test_workflow_errors.py`.

## Shared fixtures

- Shared fixtures live in `tests/conftest.py` and `tests/jira/conftest.py`.
  Use them; do not redefine them in a test module.

## Skips and flakes

- Do not use `skip`, `skipif`, `xfail` or `importorskip`. A missing
  dependency or fixture file must fail the test.

## When a test fails

- Diagnose it against intended behaviour before editing code or tests.
  The fix may span production code, shared test utilities, fixtures and
  regression coverage.
- Do not weaken assertions, widen timeouts, add sleeps or add retries to
  hide a race. Use deterministic state setup and observable readiness
  conditions.
- When a failure exposes a coverage gap, add a regression test at the most
  useful boundary.
- Verify the focused failure first, then run the affected suite and the
  relevant integration tests. Use repeated or stress runs only to test a
  specific flakiness hypothesis or verify a stability fix.

## Conventions

- pytest with `pytest-asyncio` in auto mode: write `async def test_...`.
- Never write to stdout in test code.
