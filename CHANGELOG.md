# Changelog

<!-- markdownlint-disable MD024 -->

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `get_issue` returns `duedate`

## [0.7.0] - 2026-10-11

### Added

- `update_issue` tool changes summary, description, priority, labels, and
  assignee, plus any other field through `fields` in Jira REST format. A
  `null` value in `fields` clears a field
- `delete_issue` tool permanently deletes an issue, and its subtasks when
  `delete_subtasks` is true
- Both tools are annotated as destructive and idempotent, so clients can ask
  for confirmation before running them

### Changed

- Tool registration is split across `app.py` (server instance and shared
  helpers), `server.py` (read-only tools and the entry point), and
  `write_tools.py` (tools that change Jira or local files). The launch
  command is unchanged

## [0.6.0] - 2026-10-10

### Breaking

- The Python package is now `simple_jira_mcp` (was `src`). Change
  `"args": ["-m", "src"]` to `"args": ["-m", "simple_jira_mcp"]` in MCP client
  configs and reinstall with `pip install -e ".[dev]"`
- Failed tool calls now set the MCP result's `isError` flag. The
  `{"isError": true, "error": {...}}` body is unchanged, so clients that read
  the error code keep working, but clients now see the call as failed
- Arguments that violate a tool's input schema (`limit` outside 1-100, an
  unknown `fields` value, a wrong type) are rejected by the SDK with a
  plain-text message before the tool runs, in place of `VALIDATION_ERROR`
- `JIRA_CONFIG_JSON` entries must use an `https://` URL, must not have empty
  `id`, `url`, `email`, or `token` values, and must have unique `id` values.
  The server exits at startup otherwise
- Requires MCP Python SDK 2.x (`mcp>=2.3,<3`)

### Added

- `simple-jira-mcp` console script
- Parameter descriptions, a `limit` range, and a `fields` enum in the tool
  input schemas
- Tool titles and annotations: the four read tools are marked read-only
- Server `instructions` describing `config_id` and the transition workflow
- GitHub Actions workflow running `./check.sh` on Python 3.11 and 3.14

### Changed

- One pooled HTTP client per Jira config replaces a new connection per
  request; pooled clients are closed on shutdown
- `download_attachment` streams to disk in chunks and removes the partial
  file when a download fails partway
- `download_attachment` appends the attachment ID to the filename when the
  target path already exists, so same-named attachments no longer overwrite
  each other
- JQL text is logged at DEBUG; INFO logs record only that a search ran
- Runtime and dev dependencies have version bounds; `requirements.txt` and
  `requirements-dev.txt` are removed in favor of `pyproject.toml`

### Fixed

- Fresh installs failed with `ModuleNotFoundError: mcp.server.fastmcp`
  because the unbounded `mcp` dependency resolved to 2.x
- A success response whose body is not a JSON object now returns
  `JIRA_ERROR` from `search_issues`, `get_issue`, and `create_issue`
- `JiraConfig` no longer includes the API token in its `repr`

## [0.5.0] - 2026-10-01

### Added

- `get_transitions` tool lists the workflow transitions available for an
  issue, including the fields each transition screen accepts
- `transition_issue` tool moves an issue through its workflow. The
  transition can be given by ID, name, or target status, and may carry an
  optional comment, resolution, and transition-screen fields. Unknown or
  ambiguous names return `VALIDATION_ERROR` with the valid options
- `add_comment` tool adds a plain-text comment to an issue, converted to ADF

### Documentation

- Document the three workflow tools in `README.md` and `API_REFERENCE.md`

## [0.4.0] - 2026-08-01

### Changed

- The `search_issues` tool description now names the clauses that satisfy the
  bounding check and states that scoping to a project is not required — the
  previous "Requires bounded query" wording read as a project-scope
  requirement
- `UNBOUNDED_QUERY` errors now list the accepted bounding keywords

### Added

- Optional per-config `timeout` field in `JIRA_CONFIG_JSON` (seconds,
  defaults to 30.0) controlling the HTTP timeout for that instance; a
  non-numeric or non-positive value is rejected at startup
- `list_configs` now reports each config's effective `timeout`

### Documentation

- Document the HTTP timeout: what the budget covers, why it does not bound
  a large attachment download, and which error codes a timeout surfaces as
- Document that `list_configs` never returns an error and reports
  `{"configs": []}` rather than `CONFIG_NOT_FOUND` for an empty roster
- Note that `download_attachment` buffers the whole attachment in memory
- Document that JQL values which are reserved words must be quoted
  (`project = "ON"`), a first-query trap for short project keys

## [0.3.0] - 2026-07-26

### Changed

- `search_issues` responses are now field-driven: each issue contains `key`,
  `url`, and only the requested `fields` (previously a fixed set of keys)
- ADF-to-text conversion joins adjacent inline nodes without inserting spaces
  (formatting marks no longer split words) and separates block nodes with
  blank lines instead of single spaces
- `key` is no longer selectable in `search_issues` `fields` — it is always
  returned, and requesting it now returns `VALIDATION_ERROR`
- The package installs as `src` rather than exposing `jira`, `tools`, and
  `utils` as top-level modules, so `python -m src` works outside the
  project directory

### Fixed

- JQL bound checks match bounding keywords as whole words and ignore matches
  inside quoted strings and the `ORDER BY` clause
- Attachment filename sanitization strips Windows-style path separators and
  rejects dot-only names (`.`, `..`), falling back to `attachment`
- Attachment downloads report file-write failures as `DOWNLOAD_FAILED`
  instead of raising
- `search_issues` derives `is_last` from `next_page_token` when Jira omits
  `isLast`, so clients no longer stop paginating while a page remains

## [0.2.0] - 2026-07-03

### Changed

- Reduced MCP tool schema token usage by ~50%
- Refactored issue creation to use a params object and improved ADF text
  conversion

### Removed

- Deprecated `start_at` parameter from `search_issues` (use token-based
  pagination instead)

## [0.1.0] - 2025-12-12

### Added

- Initial release
- `list_configs` tool for listing available Jira configurations
- `search_issues` tool for JQL-based issue search
- `get_issue` tool for retrieving issue details with comments and attachments
- `create_issue` tool for creating new issues
- `download_attachment` tool for downloading attachments
- Multi-configuration support via `JIRA_CONFIG_JSON` environment variable
- Input validation for issue keys, project keys, and JQL queries
- ADF (Atlassian Document Format) conversion utilities
- Structured error responses with error codes
