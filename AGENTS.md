# AGENTS.md

## Project

MCP server providing Jira Cloud integration for AI agents via stdio transport.
Built with the MCP Python SDK 2.x (`MCPServer`). See `API_REFERENCE.md` for
tool schemas, error codes, and JQL patterns.

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
file <300 / function <100 line limits. `get_prop_drilling` flags parameters
threaded through 3+ functions; `find_dead_code` (run on the project root with
`ignore_patterns: ["**/test_*.py", "**/tests/**"]`) flags unreferenced symbols
and private methods.

Install once (needs Node 22+ and `tokei`, e.g. `brew install tokei`):
`claude mcp add --scope user scopewalker-mcp -- npx -y scopewalker-mcp`.
Source and docs: <https://github.com/timohaa/scopewalker-mcp>

## Behavior

- Write the minimum code that solves the problem. Avoid speculative
  abstractions, unrelated renames, and unrelated cleanup.
- Run `./check.sh` and read a tool's tests to confirm its behavior.
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

## Key Files

- `src/simple_jira_mcp/app.py` — `MCPServer` instance and helpers shared by
  tool registrations
- `src/simple_jira_mcp/server.py` — MCP entry point, read-only tool
  registration
- `src/simple_jira_mcp/write_tools.py` — Registration of tools that change
  Jira or local files
- `src/simple_jira_mcp/schemas.py` — `Annotated` parameter types that give
  tool schemas their descriptions
- `src/simple_jira_mcp/config.py` — Configuration loading
- `src/simple_jira_mcp/tools/` — Tool implementations (one file per tool group)
- `src/simple_jira_mcp/jira/client.py` — Jira REST API v3 client; `get_client()`
  returns the pooled client for a config
- `src/simple_jira_mcp/jira/adf.py` — ADF ↔ plain text conversion
- `src/simple_jira_mcp/utils/` — Validation and error handling

## Jira API Gotchas

- **Use POST for search**: `POST /rest/api/3/search/jql`
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

- **Convert descriptions and comments**: Jira Cloud uses Atlassian Document
  Format for
  descriptions/comments. Convert ADF → plain text when returning data,
  plain text → ADF when creating. See `jira/adf.py`.

## Error Handling

Functions in `tools/` and `jira/` never raise for runtime failures. They
return the payload built by `error_response()` in
`src/simple_jira_mcp/utils/errors.py`; test for it with `is_error()`.
`tool_result()` in `app.py` turns that payload into a `CallToolResult` with
the protocol `is_error` flag set, keeping the JSON body as content.
Schema violations are rejected by the SDK before the tool function runs.
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

## Writing Style

Apply these rules to chat responses, commit messages, PR descriptions, and
docs. Rephrasing a banned rhetorical pattern still violates the rule.

- No antithesis filler ("it's not X, it's Y", "isn't just X, it's Y") —
  implies a distinction without stating one.
- No preamble that announces insight instead of giving it ("here's the
  thing", "the real question is", "worth noting", "to be clear", "let me be
  direct").
- No closing aphorisms ("that's the whole game", "that's the tell").
- No sentence fragments used for emphasis, no sentence that exists only for
  rhythm.
- No vague jargon standing in for a plain claim ("load-bearing", "surface
  area", "first-class", "at scale", "does the heavy lifting").
- Do not use "gate" or "gating" as generic verbs or metaphors. Reserve them
  for actual gates, such as physical, noise, or logic gates.
- No intensifiers propping up a claim that should stand on its own
  ("genuinely", "truly", "actually", "honestly").
- No rule-of-three or "two things:" list where an item is filler.
- Lead with the action, not the topic: "I'd skip the architecture doc," not
  "The architecture doc is the bit I'd skip."
- One idea per sentence; prefer sentences under ~20 words.

Examples:

- "Two honest caveats, because they are the actual insight." -> "Note that"
- "Watch what dissolves. Each piece of the current machinery becomes a line
  of ordinary code." -> "The current machinery simplifies to"
