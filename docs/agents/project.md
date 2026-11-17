# Project

MCP server providing Jira Cloud integration for AI agents via stdio transport.
See `API_REFERENCE.md` for
tool schemas, error codes, and JQL patterns.

## No stdout

**NEVER** write to stdout — not `print()`, not any library default.
Stdout is the MCP JSON-RPC transport channel. Any stray output corrupts the
protocol and breaks the server silently.
Use `stderr` via the `logging` module for all diagnostics.

## Commands

`./check.sh` runs lint, mypy and the tests; `./check.sh -h` lists the flags
that run one of them, coverage or the lint auto-fix.

## Size limits

Run `check_thresholds` (scopewalker MCP tool) before committing to enforce
file <300 / function <100 line limits. `get_prop_drilling` flags parameters
threaded through 3+ functions; `find_dead_code` (run on the project root with
`ignore_patterns: ["**/test_*.py", "**/tests/**"]`) flags unreferenced symbols
and private methods.

A limit never blocks or shrinks a requested change. If a change would push a
file or function past a limit, refactor it first so the change fits, or make
the change and refactor afterwards. In rare cases a file or function may
stay over a limit, but only for a valid reason recorded in a comment at that
code.

Install once (needs `tokei`, e.g. `brew install tokei`):
`claude mcp add --scope user scopewalker-mcp -- npx -y scopewalker-mcp`.
Source and docs: <https://github.com/timohaa/scopewalker-mcp>

## Behavior

- **Never create `_enhanced`, `_v2`, or `_new` duplicate file variants** —
  edit the original file.
- **Do not bump the version.** Leave `version` in `pyproject.toml` unchanged
  and add no dated release heading to `CHANGELOG.md`, even for a `feat` or a
  breaking change. Record user-visible changes under `## [Unreleased]`.
  Cut a release only when the user asks for one, as a separate
  `chore: Release vX.Y.Z` commit.

Prefer LSP over Grep/Read for code navigation (`workspaceSymbol`,
`findReferences`, `goToDefinition`, `hover`). Use Grep only for text/pattern
searches.

## Error Handling

Functions in `tools/` and `jira/` never raise for runtime failures. They
return the payload built by `error_response()` in
`src/simple_jira_mcp/utils/errors.py`; test for it with `is_error()`.
`tool_result()` in `app.py` turns that payload into a `CallToolResult` with
the protocol `is_error` flag set, keeping the JSON body as content.
Schema violations are rejected by the SDK before the tool function runs.
Full error code reference: `API_REFERENCE.md`.

## Security

- Never log or expose API tokens
- Sanitize attachment filenames (prevent directory traversal)
