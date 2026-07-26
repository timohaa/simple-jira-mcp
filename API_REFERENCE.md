# API Reference

Authoritative reference for the Jira MCP tools.

## Tools

### list_configs

- Purpose: List configured Jira instances.
- Returns: `{"configs": [{"id": str, "url": str, "default": bool}, ...]}`.

### search_issues

- Purpose: Run bounded JQL queries (semicolon and newline are rejected).
- Inputs: `jql` (required, must include a filter), `config_id` (optional),
  `limit` 1-100 (default 50), `next_page_token` (cursor pagination),
  `fields` (optional allowlist, forwarded to Jira as the requested fields).
  Pagination is cursor-based via `next_page_token` (Jira API v3 does not
  support offset pagination).
- Allowed `fields` values: `summary`, `status`, `assignee`, `reporter`,
  `priority`, `resolution`, `issuetype`, `labels`, `created`, `updated`,
  `description`, `comment`, `attachment`, `project`. Any other value
  returns `VALIDATION_ERROR`. `key` is not selectable — it is always
  returned. When `fields` is omitted the default set is
  `summary`, `status`, `assignee`, `priority`, `updated`, `created`,
  `labels`, `issuetype`.
- Returns: `{"issues": [...], "is_last": bool, "next_page_token": str?}`.
  The Jira `/search/jql` endpoint provides no total count; use `is_last` /
  `next_page_token` to paginate.
  Each issue contains `key`, `url`, and only the requested fields — the
  response shape follows `fields`. A few output keys are renamed:
  `issuetype` → `issue_type`, `comment` → `comments`, `attachment` →
  `attachments`; `project` returns the project key. `comments` and
  `attachments` use the same shape as get_issue.
- Errors: `INVALID_JQL`, `UNBOUNDED_QUERY`, `VALIDATION_ERROR`, `AUTH_FAILED`,
  `CONFIG_NOT_FOUND`, `RATE_LIMITED`, `JIRA_ERROR`.

### get_issue

- Purpose: Retrieve a single issue with optional comments and attachments.
- Inputs: `issue_key` (PROJECT-123), `config_id` (optional),
  `include_comments` (default true), `include_attachments` (default true).
- Returns: Plain-text summary/description, reporter/assignee, status, priority,
  issue_type, labels, created/updated/resolved dates, url, optional `comments`
  (`author`, `created`, `body`) and `attachments` (`id`, `filename`, `size_kb`,
  `mime_type`, `created`). Pass an attachment `id` to `download_attachment`.
- Errors: `ISSUE_NOT_FOUND`, `VALIDATION_ERROR`, `AUTH_FAILED`, `CONFIG_NOT_FOUND`,
  `RATE_LIMITED`, `JIRA_ERROR`.

### create_issue

- Purpose: Create a new issue.
- Inputs: `project_key` (PROJECT), `summary` (<=255 chars), `issue_type`
  (default Task), `description` (plain text, converted to ADF), `priority`,
  `labels`, `assignee_account_id`, `config_id` (optional).
- Returns: `{"key": str, "id": str, "url": str}`.
- Errors: `PROJECT_NOT_FOUND`, `INVALID_ISSUE_TYPE`, `INVALID_PRIORITY`,
  `AUTH_FAILED`, `CONFIG_NOT_FOUND`, `VALIDATION_ERROR`, `RATE_LIMITED`,
  `JIRA_ERROR`.

### download_attachment

- Purpose: Download an attachment to disk.
- Inputs: `issue_key` (PROJECT-123), `attachment_id` (numeric string),
  `output_dir` (must exist when provided, defaults to CWD), `config_id` (optional).
- Behavior: Resolves the filename from the issue's attachment metadata, then
  saves to `<output_dir>/<issue_key>/<sanitized filename>`, creating the
  `<issue_key>` subdirectory if needed.
- Returns: `{"success": true, "filename": str, "path": str, "size_kb": float,
  "mime_type": str}`. `filename` is the sanitized name and `mime_type` comes
  from the download response's `content-type` header.
- Errors: `ATTACHMENT_NOT_FOUND`, `ISSUE_NOT_FOUND`, `AUTH_FAILED`,
  `CONFIG_NOT_FOUND`, `DOWNLOAD_FAILED`, `VALIDATION_ERROR`, `RATE_LIMITED`,
  `JIRA_ERROR`.

## Error Codes

| Code                   | Description                         |
|------------------------|-------------------------------------|
| `AUTH_FAILED`          | Invalid credentials                 |
| `CONFIG_NOT_FOUND`     | Unknown config_id or missing config |
| `ISSUE_NOT_FOUND`      | Issue key does not exist            |
| `PROJECT_NOT_FOUND`    | Project key does not exist          |
| `ATTACHMENT_NOT_FOUND` | Attachment ID not found on issue    |
| `INVALID_JQL`          | Malformed JQL                       |
| `UNBOUNDED_QUERY`      | Query lacks required filters        |
| `INVALID_ISSUE_TYPE`   | Issue type not available in project |
| `INVALID_PRIORITY`     | Priority not recognized             |
| `VALIDATION_ERROR`     | Input validation failure            |
| `DOWNLOAD_FAILED`      | Attachment download failed          |
| `RATE_LIMITED`         | Jira API rate limit exceeded        |
| `JIRA_ERROR`           | Unexpected Jira error               |

## Validation Notes

- JQL must include at least one bounding filter; semicolons and newlines are
  rejected.
- Bounding keywords: `project`, `assignee`, `reporter`, `created`, `updated`,
  `resolved`, `status`, `type`, `issuetype`, `priority`, `key`, `id`. They are
  matched as whole words outside quoted strings and outside the `ORDER BY`
  clause, so `text ~ "project plan" ORDER BY created` is still unbounded.
- `limit` must be 1-100.
- `issue_key` pattern: `^[A-Z][A-Z0-9]+-\d+$`;
  `project_key`: `^[A-Z][A-Z0-9]+$`. Both are trimmed and upper-cased first.
- `attachment_id` must be numeric.
- `output_dir` must exist and be a directory when provided; when omitted the
  current working directory is used.
- Filenames are sanitized before writing: any directory component (`/` or `\`)
  is dropped, `: < > " | ? *` and NUL become `_`, and empty or dot-only names
  fall back to `attachment`.

## Common JQL Patterns

- Updated in range: `updated >= "2025-01-15" AND updated < "2025-01-16"`
- Created in range: `created >= "2025-01-01" AND created < "2025-02-01"`
- Current user involvement: `assignee = currentUser() OR reporter = currentUser()`
- Project filter: `project = ONE`
- Keyword search: `project = ONE AND text ~ "questionnaire"`
- Completed in window:
  `project = ONE AND status = "Done" AND resolved >= "2025-10-15"
  AND resolved < "2025-10-31"`
