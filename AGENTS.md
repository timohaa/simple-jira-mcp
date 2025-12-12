# AGENTS.md

## Use Scopewalker MCP Tools

Use scopewalker-mcp tools to understand and validate the code:

- `get_directory_tree` - Project structure
- `get_code_inventory` - Classes, functions, exports
- `get_line_counts` / `get_function_line_counts` - Line metrics
- `check_thresholds` - Verify size limits (files <300, functions <100 lines)
- `get_complexity_metrics` - Find code needing refactoring
- `get_code_smells` - Find TODO, FIXME, HACK markers
- `get_git_context` - Changed files, hotspots, blame

Run `check_thresholds` before committing.

## MCP Server Critical Rules

### STDIO Transport

**CRITICAL:** This is an MCP server using stdio transport.

- **NEVER** write to stdout. This includes:
  - `print()` statements in Python
  - Any library that writes to stdout by default
- Writing to stdout corrupts JSON-RPC messages and breaks the MCP protocol.
- **ALWAYS** use `stderr` for logging via the `logging` module.

### Tool Implementation

- All tools must validate inputs before execution.
- Return structured JSON responses matching the schemas in `API_REFERENCE.md`.
- Use the two-tier error model:
  - Protocol errors for invalid tool calls (JSON-RPC errors)
  - Execution errors with `isError: true` for runtime failures
- Never expose internal errors or stack traces to clients.

## Commands

```bash
./check.sh              # Run all checks (lint + mypy + tests)
./check.sh -l           # Ruff linting only
./check.sh -m           # Mypy only
./check.sh -t           # Tests only
./check.sh -c           # Tests with coverage
./check.sh -f           # Auto-fix linting issues
```

## Architecture

MCP server providing Jira Cloud integration for AI agents.

### Key Files

- `API_REFERENCE.md` - Tool inputs/outputs, error codes, JQL patterns
- `src/server.py` - MCP server entry point (FastMCP)
- `src/config.py` - Configuration loading
- `src/tools/` - Tool implementations
- `src/jira/client.py` - Jira API client
- `src/jira/adf.py` - ADF conversion utilities
- `src/utils/` - Validation and error handling

## Key Patterns

### Jira API

- REST API v3 (`/rest/api/3/`)
- Search: `POST /rest/api/3/search/jql` (not GET)
- All queries must be "bounded" (include at least one filter)

### Date Handling

Jira interprets dates as midnight. To include a full day:

```python
jql = 'updated >= "2025-01-15" AND updated < "2025-01-16"'
# NOT: updated <= "2025-01-15" (only includes midnight)
```

### Atlassian Document Format (ADF)

Jira Cloud uses ADF for descriptions and comments. See `src/jira/adf.py`.
Convert ADF to plain text when returning data, plain text to ADF when
creating issues.

### Error Handling

Structured error responses. See `API_REFERENCE.md` for error codes.

## Security

- Never log or expose API tokens
- Sanitize attachment filenames (prevent directory traversal)

## Testing

- Mock Jira API responses
- Test error conditions
- Never test against production Jira
