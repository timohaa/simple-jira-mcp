# Jira API Gotchas

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
