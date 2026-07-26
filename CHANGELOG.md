# Changelog

<!-- markdownlint-disable MD024 -->

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

## [0.1.0] - 2025-12-08

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
