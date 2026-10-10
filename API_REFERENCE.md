# API Reference

Use this reference for tool inputs, outputs, errors, and JQL examples.

## Results and Errors

Every tool returns a JSON object, as both text content and structured
content. A failed call sets the MCP result's `isError` flag and returns:

```json
{"isError": true, "error": {"code": "ISSUE_NOT_FOUND", "message": "Issue not found"}}
```

The MCP SDK rejects arguments that violate a tool's input schema before the
tool runs. Examples include missing required arguments, wrong types,
`limit` outside 1-100, and `fields` values outside the allowlist. These
results set `isError` and contain the SDK's plain-text validation message.

Tool annotations: `list_configs`, `search_issues`, `get_issue`, and
`get_transitions` are marked read-only. `update_issue` and `delete_issue`
are marked destructive and idempotent. The other four are marked
non-destructive and non-idempotent. Repeating an idempotent call leaves
Jira in the same state. For example, repeating `delete_issue` leaves the
issue deleted and returns `ISSUE_NOT_FOUND`.

## Tools

### list_configs

- Purpose: List configured Jira instances.
- Returns: `{"configs": [{"id": str, "url": str, "default": bool,
  "timeout": float}, ...]}`. Credentials are never included.
- Errors: none. With no configs loaded, this tool returns `{"configs": []}`.
  The server exits at startup if `JIRA_CONFIG_JSON` is unset, malformed, or
  empty.

### search_issues

- Purpose: Run bounded JQL queries (semicolon and newline are rejected).
- Inputs: `jql` (required, must include a bounding clause — see Validation
  Notes; scoping to a project is *not* required), `config_id` (optional),
  `limit` 1-100 (default 50), `next_page_token` (cursor pagination),
  `fields` (optional allowlist, forwarded to Jira as the requested fields).
  Pagination is cursor-based via `next_page_token` (Jira API v3 does not
  support offset pagination).
- Allowed `fields` values: `summary`, `status`, `assignee`, `reporter`,
  `priority`, `resolution`, `issuetype`, `labels`, `created`, `updated`,
  `description`, `comment`, `attachment`, `project`. The input schema lists
  these as an enum and rejects other values. Every issue includes `key`,
  which cannot be selected through `fields`. When `fields` is omitted, the
  default set is `summary`, `status`, `assignee`, `priority`, `updated`, `created`,
  `labels`, `issuetype`.
- Returns: `{"issues": [...], "is_last": bool, "next_page_token": str?}`.
  The Jira `/search/jql` endpoint provides no total count; use `is_last` /
  `next_page_token` to paginate.
  Each issue contains `key`, `url`, and only the requested fields.
  These fields have different output keys:
  `issuetype` → `issue_type`, `comment` → `comments`, `attachment` →
  `attachments`; `project` returns the project key. `comments` and
  `attachments` use the same structure as `get_issue`.
- Errors: `INVALID_JQL`, `UNBOUNDED_QUERY`, `VALIDATION_ERROR`, `AUTH_FAILED`,
  `CONFIG_NOT_FOUND`, `RATE_LIMITED`, `JIRA_ERROR`.

### get_issue

- Purpose: Retrieve a single issue with optional comments and attachments.
- Inputs: `issue_key` (PROJECT-123), `config_id` (optional),
  `include_comments` (default true), `include_attachments` (default true).
- Returns: `key`, plain-text summary/description, reporter/assignee, status,
  priority, issue_type, labels, created/updated/resolved dates, `duedate`
  (`YYYY-MM-DD` or null), url, optional `comments`
  (`author`, `created`, `body`) and `attachments` (`id`, `filename`, `size_kb`,
  `mime_type`, `created`). Pass an attachment `id` to `download_attachment`.
- Errors: `ISSUE_NOT_FOUND`, `VALIDATION_ERROR`, `AUTH_FAILED`,
  `CONFIG_NOT_FOUND`, `RATE_LIMITED`, `JIRA_ERROR`.

### create_issue

- Purpose: Create a new issue.
- Inputs: `project_key` (PROJECT), `summary` (<=255 chars), `issue_type`
  (default Task), `description` (plain text, converted to ADF), `priority`,
  `labels`, `assignee_account_id`, `config_id` (optional).
- Returns: `{"key": str, "id": str, "url": str}`.
- Errors: `PROJECT_NOT_FOUND`, `INVALID_ISSUE_TYPE`, `INVALID_PRIORITY`,
  `AUTH_FAILED`, `CONFIG_NOT_FOUND`, `VALIDATION_ERROR`, `RATE_LIMITED`,
  `JIRA_ERROR`.

### update_issue

- Purpose: Change fields on an existing issue.
- Inputs: `issue_key` (PROJECT-123), `summary` (<=255 chars), `description`
  (plain text, converted to ADF), `priority`, `labels`, `assignee_account_id`,
  `fields` (dict of Jira field IDs to native JSON values), `config_id`. All but
  `issue_key` are optional, and at least one field must be given.
- Behavior: Omitted parameters leave their field unchanged. `labels` replaces
  the current labels, and `[]` removes them all. An empty `description`
  replaces the description with an empty document. Put any other field in
  `fields`. A `null` value there clears the field, for example
  `{"assignee": null}` to unassign. A field given both directly and in
  `fields` returns `VALIDATION_ERROR`. Status cannot be changed here; use
  `transition_issue`.
- Endpoint: `PUT /rest/api/3/issue/{key}`.
- Returns: `{"key": str, "url": str, "updated": [field_id, ...]}`. `updated`
  lists the field IDs sent to Jira, sorted.
- Errors: `ISSUE_NOT_FOUND`, `VALIDATION_ERROR` (including fields Jira rejects),
  `INVALID_PRIORITY`, `AUTH_FAILED`, `CONFIG_NOT_FOUND`, `RATE_LIMITED`,
  `JIRA_ERROR`. `INVALID_PRIORITY` names the rejected `priority` and lists
  allowed names from `GET /rest/api/3/issue/{key}/editmeta`.

Example inputs:

```json
{
  "issue_key": "ONE-123",
  "summary": "Login fails on Safari 18",
  "labels": ["browser", "login"],
  "fields": {"duedate": "2026-11-01", "assignee": null}
}
```

### delete_issue

- Purpose: Permanently delete an issue. Jira cannot restore a deleted issue.
- Inputs: `issue_key` (PROJECT-123), `delete_subtasks` (default false),
  `config_id` (optional).
- Behavior: Deleting an issue with subtasks requires `delete_subtasks: true`;
  otherwise, the tool returns `VALIDATION_ERROR`.
  Deleting an issue that is already deleted returns `ISSUE_NOT_FOUND`.
- Endpoint: `DELETE /rest/api/3/issue/{key}?deleteSubtasks=true|false`.
- Returns: `{"key": str, "deleted": true}`.
- Errors: `ISSUE_NOT_FOUND`, `VALIDATION_ERROR`, `AUTH_FAILED`,
  `CONFIG_NOT_FOUND`, `RATE_LIMITED`, `JIRA_ERROR` (including a missing
  Delete Issues permission, with Jira's message).

### get_transitions

- Purpose: List transitions available to the current user for an issue.
- Inputs: `issue_key` (PROJECT-123), `config_id` (optional).
- Endpoint: `GET /rest/api/3/issue/{key}/transitions?expand=transitions.fields`.
- Returns: `{"transitions": [{"id": str, "name": str, "status": str,
  "fields": {field_id: metadata}}, ...]}`. `status` is the target status name.
  Screen field metadata includes `required`, `name`, `schema`, `operations`,
  and `allowedValues` when supplied by Jira. Required fields have
  `required: true`. Transitions without screen fields return `fields: {}`.
  An issue with no available transitions returns `transitions: []`.
- Errors: `ISSUE_NOT_FOUND`, `VALIDATION_ERROR`, `AUTH_FAILED`,
  `CONFIG_NOT_FOUND`, `RATE_LIMITED`, `JIRA_ERROR`.

### transition_issue

- Purpose: Transition an issue, optionally setting screen fields and adding a
  comment.
- Inputs: `issue_key` (PROJECT-123), `transition` (required string), `comment`
  (optional plain text), `resolution` (optional resolution name), `fields`
  (optional dict of Jira field IDs to native JSON values), `config_id`
  (optional).
- Selection: An exact transition ID takes precedence. Otherwise, match the
  transition name or target status name case-insensitively. Unknown or ambiguous
  names return `VALIDATION_ERROR` with the available IDs, names, and target
  statuses. Use an ID when several transitions lead to the same status.
- Endpoint: Fetch expanded transition metadata, then
  `POST /rest/api/3/issue/{key}/transitions`. The tool converts an optional
  comment to ADF. It includes the comment in `update.comment` when metadata lists
  `comment`. Otherwise, the tool posts it afterwards to
  `POST /rest/api/3/issue/{key}/comment`.
- Fields: `resolution` becomes `fields.resolution: {"name": resolution}`.
  Supplied fields must appear in the selected transition's screen metadata and
  support the `set` operation. Unsupported fields return `VALIDATION_ERROR`
  before posting. Supply resolution either directly or in `fields`, never both.
  Jira validates required fields, defaults, allowed values, and workflow rules.
  See [Atlassian's transition API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/#api-rest-api-3-issue-issueidorkey-transitions-post).
- Returns: `{"key": str, "status": str, "resolution": str | null,
  "resolutiondate": str | null}`. After the transition, the tool fetches
  Jira's current `status,resolution,resolutiondate` values.
- Dates: Jira sets `resolutiondate` itself; the API cannot edit it. Attempts to
  supply it in `fields` return `VALIDATION_ERROR`. Record the actual completion
  date in the comment, for example `"Completed on 2026-09-30; verified today."`.
- Errors: `ISSUE_NOT_FOUND`, `VALIDATION_ERROR`, `AUTH_FAILED`,
  `CONFIG_NOT_FOUND`, `RATE_LIMITED`, `JIRA_ERROR`. Errors after a successful
  transition say it succeeded, whether the separate comment or read failed.
  Read the issue before retrying.

Example inputs:

```json
{
  "issue_key": "ONE-123",
  "transition": "Done",
  "comment": "Completed on 2026-09-30; verified today.",
  "resolution": "Fixed"
}
```

### add_comment

- Purpose: Add a comment to an issue.
- Inputs: `issue_key` (PROJECT-123), `body` (required non-empty plain text),
  `config_id` (optional).
- Endpoint: `POST /rest/api/3/issue/{key}/comment` with an ADF `body`.
- Returns: `{"id": str, "created": str}` using Jira's comment ID and timestamp.
- Errors: `ISSUE_NOT_FOUND`, `VALIDATION_ERROR`, `AUTH_FAILED`,
  `CONFIG_NOT_FOUND`, `RATE_LIMITED`, `JIRA_ERROR`.

### download_attachment

- Purpose: Download an attachment to disk.
- Inputs: `issue_key` (PROJECT-123), `attachment_id` (numeric string),
  `output_dir` (must exist when provided, defaults to CWD), `config_id`
  (optional).
- Behavior: Resolves the filename from the issue's attachment metadata, then
  saves to `<output_dir>/<issue_key>/<sanitized filename>`, creating the
  `<issue_key>` subdirectory if needed. If that path already exists, the
  attachment ID is appended to the stem (`log.txt` → `log-10042.txt`) so
  same-named attachments on one issue do not overwrite each other.
  Downloading the same attachment again overwrites its suffixed copy.
- Returns: `{"success": true, "filename": str, "path": str, "size_kb": float,
  "mime_type": str}`. `filename` is the sanitized name and `mime_type` comes
  from the download response's `content-type` header.
- The body is streamed to disk in chunks, so memory use does not grow with
  attachment size. There is no size cap. A download that fails partway
  removes its partial file.
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

## Configuration Rules

`JIRA_CONFIG_JSON` is validated at startup; the server exits on any failure.

- `id`, `url`, `email`, and `token` are required and must not be empty.
  Surrounding whitespace is trimmed.
- `url` must start with `https://`. Basic auth over plain HTTP would expose
  the API token.
- `id` values must be unique.
- `timeout` is optional; see Timeouts.

## Timeouts

- Every Jira request uses the `timeout` of its config, an optional field in
  each `JIRA_CONFIG_JSON` entry. It defaults to `30.0` seconds and must be a
  positive number; anything else fails at startup.
- Connect, read, write, and pool each receive the full `timeout` value.
  A request can exceed one `timeout` interval in total.
- The read timeout limits the wait for each chunk of the response body.
  An attachment download can continue while chunks arrive within that limit,
  regardless of its total duration.
- Timeouts return `JIRA_ERROR` from `search_issues`, `get_issue`,
  `create_issue`, `update_issue`, `delete_issue`, `get_transitions`,
  `transition_issue`, and `add_comment`.
- `download_attachment` returns `JIRA_ERROR` if its initial metadata fetch
  times out. A timeout during the file transfer returns `DOWNLOAD_FAILED`.
- Timeout messages come from the underlying httpx exception. They use the
  same error codes as other connection failures.

## Validation Notes

- JQL must include at least one bounding filter; semicolons and newlines are
  rejected.
- Bounding keywords: `project`, `assignee`, `reporter`, `created`, `updated`,
  `resolved`, `status`, `type`, `issuetype`, `priority`, `key`, `id`. They are
  matched as whole words outside quoted strings and outside the `ORDER BY`
  clause, so `text ~ "project plan" ORDER BY created` is still unbounded.
- Any one of those keywords satisfies the check. For example,
  `status = "Done"` searches every project the account can see.
- `limit` must be 1-100 (enforced by the input schema).
- `issue_key` pattern: `^[A-Z][A-Z0-9]+-\d+$`;
  `project_key`: `^[A-Z][A-Z0-9]+$`. Both are trimmed and upper-cased first.
- `attachment_id` must be numeric.
- `transition` and comment `body` must not be empty or whitespace-only.
  Optional transition `comment` and `resolution` must also be non-empty when
  supplied.
- `update_issue` rejects an empty or whitespace-only `summary`, `priority`, or
  `assignee_account_id`. To unassign, pass `fields: {"assignee": null}`.
- `output_dir` must exist and be a directory when provided; when omitted the
  current working directory is used.
- Filenames are sanitized before writing. Directory components (`/` or `\`)
  are dropped. The characters `: < > " | ? *` and NUL become `_`.
  Empty or dot-only names fall back to `attachment`.

## Common JQL Patterns

Quote JQL values that are reserved words. Unquoted reserved values cause
`INVALID_JQL` with a character offset. Reserved words include `ON`, `IN`,
`IS`, `TO`, `BY`, `AND`, `OR`, `NOT`, `NULL`, `EMPTY`, `WAS`, `CF`, and `FROM`.
Always quote project keys to avoid these conflicts: `project = "ON"`.

- Updated in range: `updated >= "2025-01-15" AND updated < "2025-01-16"`
- Created in range: `created >= "2025-01-01" AND created < "2025-02-01"`
- Current user involvement: `assignee = currentUser() OR reporter = currentUser()`
- Project filter: `project = "ONE"`
- Keyword search: `project = "ONE" AND text ~ "questionnaire"`
- Completed in window:
  `project = "ONE" AND status = "Done" AND resolved >= "2025-10-15"
  AND resolved < "2025-10-31"`
