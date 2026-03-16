# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
