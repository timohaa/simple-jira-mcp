# AGENTS.md

## Project

MCP server providing Jira Cloud integration for AI agents via stdio transport.
Built with FastMCP (Python). See `API_REFERENCE.md` for tool schemas, error
codes, and JQL patterns.

## Critical: No stdout

**NEVER** write to stdout — not `print()`, not any library default.
Stdout is the MCP JSON-RPC transport channel. Any stray output corrupts the
protocol and breaks the server silently.
Use `stderr` via the `logging` module for all diagnostics.

## Commands

```bash
./check.sh              # All checks (lint + mypy + tests)
./check.sh -l           # Ruff lint only
./check.sh -m           # Mypy only
./check.sh -t           # Tests only
./check.sh -c           # Tests with coverage
./check.sh -f           # Auto-fix lint
./check.sh -a           # Explicitly run all checks
./check.sh -h           # Show help
```

Run `check_thresholds` (scopewalker MCP tool) before committing to enforce
file <300 / function <100 line limits.

## Behavior

- **Minimum footprint.** Write the minimum code that solves the problem —
  no speculative abstractions, no drive-by renames, no unrelated cleanup
  bundled into the same change.
- **Verify, don't trust.** `./check.sh` passing is necessary but not
  sufficient — read a tool's tests to confirm its actual behavior.
- **Never create `_enhanced`, `_v2`, or `_new` duplicate file variants** —
  edit the original file.

Prefer LSP over Grep/Read for code navigation (`workspaceSymbol`,
`findReferences`, `goToDefinition`, `hover`). Use Grep only for text/pattern
searches.

## Key Files

- `src/server.py` — MCP entry point (FastMCP)
- `src/config.py` — Configuration loading
- `src/tools/` — Tool implementations (one file per tool group)
- `src/jira/client.py` — Jira REST API v3 client
- `src/jira/adf.py` — ADF ↔ plain text conversion
- `src/utils/` — Validation and error handling

## Jira API Gotchas

These are non-obvious behaviors that cause real bugs:

- **Search is POST, not GET**: `POST /rest/api/3/search/jql`
- **All queries must be bounded** — always include at least one filter
  (project, assignee, date range, etc.). Any one filter is enough; the query
  need not be scoped to a project.
- **Quote reserved words in JQL values** — `project = "ON"` works,
  `project = ON` fails, because `ON` is a JQL reserved word (as are `IN`,
  `IS`, `TO`, `BY`, `WAS`, `CF`, …). Quoting is always safe.
- **Date boundaries are exclusive at midnight**:

  ```python
  # To include all of Jan 15:
  jql = 'updated >= "2025-01-15" AND updated < "2025-01-16"'
  # NOT: updated <= "2025-01-15" (only matches midnight)
  ```

- **ADF, not plain text**: Jira Cloud uses Atlassian Document Format for
  descriptions/comments. Convert ADF → plain text when returning data,
  plain text → ADF when creating. See `src/jira/adf.py`.

## Error Handling

Two-tier model: protocol errors (JSON-RPC) for invalid tool calls, and an
in-band `isError: true` field in the returned payload (built by
`error_response()` in `src/utils/errors.py`) for runtime failures — tools
never raise, so the MCP protocol-level error flag is not set.
Full error code reference: `API_REFERENCE.md`.

## Refactoring Safety

Before major refactoring:

1. `./check.sh -c` — verify test coverage on affected code
2. If coverage is insufficient, **write tests first**
3. After refactoring, `./check.sh -t` to confirm correctness

## Security

- Never log or expose API tokens
- Sanitize attachment filenames (prevent directory traversal)

## Testing

- Mock Jira API responses — never hit production Jira
- Test error conditions, not just happy paths
