# Simple Jira MCP

A Model Context Protocol (MCP) server that provides Jira Cloud integration
for AI agents.

## Features

- Search issues using JQL (Jira Query Language)
- Retrieve issue details with comments and attachments
- Create new issues
- Download attachments
- Support for multiple Jira configurations

## Why not the official Atlassian MCP server?

Atlassian ships an official remote server
([atlassian/atlassian-mcp-server](https://github.com/atlassian/atlassian-mcp-server)).
It covers far more ground — Confluence, JSM, Bitbucket, Compass, and issue
updates and transitions — with per-user OAuth scoping (API tokens optional)
and nothing for you to host. **If you need that breadth, use it.**

This server is worth choosing when:

- **You work across separate Jira instances.** `JIRA_CONFIG_JSON` takes a
  list and every tool that reaches Jira accepts `config_id`. The official
  server authorizes one Atlassian identity per connection.
- **You need attachment files on disk.** The official server has no
  attachment operations.
- **No org admin available.** The official server needs one — either to
  enable Rovo on a verified business domain (OAuth) or to explicitly enable
  its API-token authentication. This one needs only your own API token.
- **Tool-surface size matters.** Five tools instead of ~16 Jira tools plus
  four other products, a `fields` allowlist on search, and ADF flattened to
  plain text — less context spent per request.
- **You want a small blast radius.** Search, read, create, download. No
  delete, no bulk mutation, no cross-product writes.

Trade-offs, stated plainly: no Confluence or other Atlassian products, no way
to update or transition an existing issue, a shared API token rather than
per-user OAuth, and you maintain it yourself.

## Requirements

- Python 3.11+
- Jira Cloud account with API token

## Installation

```bash
git clone https://github.com/timohaa/simple-jira-mcp.git
cd simple-jira-mcp
python -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows
# venv\Scripts\activate

pip install -e ".[dev]"
```

## Configuration

Set the `JIRA_CONFIG_JSON` environment variable with your Jira credentials:

```bash
export JIRA_CONFIG_JSON='[
  {
    "id": "work",
    "url": "https://your-domain.atlassian.net",
    "email": "your-email@example.com",
    "token": "your-api-token",
    "timeout": 60
  }
]'
```

Generate an API token at: <https://id.atlassian.com/manage-profile/security/api-tokens>

`timeout` is optional and per-instance: seconds to allow for each HTTP phase,
defaulting to 30. Raise it for a slow instance or large attachments. It must be
a positive number — the server refuses to start otherwise. See
[API_REFERENCE.md](API_REFERENCE.md) for exactly what the budget covers.

## AI Tool Integration

In every snippet below, replace `/path/to/simple-jira-mcp` with your checkout
path. The `command` must be the venv interpreter created during installation —
a bare `python` only works if the ambient interpreter already has `mcp` and
`httpx` installed.

`cwd` is not needed to start the server (since 0.3.0 `python -m src` resolves
from the installed package regardless of directory), but it sets where
`download_attachment` saves files when `output_dir` is omitted. Without it,
downloads land in whatever directory the client launched the server from.

### Claude Desktop

| Platform | Config Path                                                       |
|----------|-------------------------------------------------------------------|
| macOS    | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux    | `~/.config/Claude/claude_desktop_config.json`                     |
| Windows  | `%APPDATA%\Claude\claude_desktop_config.json`                     |

```json
{
  "mcpServers": {
    "jira": {
      "command": "/path/to/simple-jira-mcp/venv/bin/python",
      "args": ["-m", "src"],
      "cwd": "/path/to/simple-jira-mcp",
      "env": {
        "JIRA_CONFIG_JSON": "[{\"id\": \"work\", \"url\": \"https://your-domain.atlassian.net\", \"email\": \"your-email@example.com\", \"token\": \"your-api-token\"}]"
      }
    }
  }
}
```

### Claude Code (CLI)

Edit `~/.claude.json`:

```json
{
  "mcpServers": {
    "jira": {
      "command": "/path/to/simple-jira-mcp/venv/bin/python",
      "args": ["-m", "src"],
      "cwd": "/path/to/simple-jira-mcp",
      "env": {
        "JIRA_CONFIG_JSON": "[{\"id\": \"work\", \"url\": \"https://your-domain.atlassian.net\", \"email\": \"your-email@example.com\", \"token\": \"your-api-token\"}]"
      }
    }
  }
}
```

Verify with `claude mcp list`.

### Gemini CLI

Config file: `~/.gemini/settings.json`

```json
{
  "mcpServers": {
    "jira": {
      "command": "/path/to/simple-jira-mcp/venv/bin/python",
      "args": ["-m", "src"],
      "cwd": "/path/to/simple-jira-mcp",
      "env": {
        "JIRA_CONFIG_JSON": "[{\"id\": \"work\", \"url\": \"https://your-domain.atlassian.net\", \"email\": \"your-email@example.com\", \"token\": \"your-api-token\"}]"
      }
    }
  }
}
```

Verify with `/mcp` command in Gemini CLI.

### OpenAI Codex CLI

Config file: `~/.codex/config.toml`

```toml
[mcp_servers.jira]
command = "/path/to/simple-jira-mcp/venv/bin/python"
args = ["-m", "src"]
cwd = "/path/to/simple-jira-mcp"

[mcp_servers.jira.env]
JIRA_CONFIG_JSON = '[{"id": "work", "url": "https://your-domain.atlassian.net", "email": "your-email@example.com", "token": "your-api-token"}]'
```

### Cursor

| Scope   | Config Path          |
|---------|----------------------|
| Global  | `~/.cursor/mcp.json` |
| Project | `.cursor/mcp.json`   |

```json
{
  "mcpServers": {
    "jira": {
      "command": "/path/to/simple-jira-mcp/venv/bin/python",
      "args": ["-m", "src"],
      "cwd": "/path/to/simple-jira-mcp",
      "env": {
        "JIRA_CONFIG_JSON": "[{\"id\": \"work\", \"url\": \"https://your-domain.atlassian.net\", \"email\": \"your-email@example.com\", \"token\": \"your-api-token\"}]"
      }
    }
  }
}
```

Access via Cursor Settings > MCP.

### Windsurf (Codeium)

| Platform    | Config Path                                       |
|-------------|---------------------------------------------------|
| macOS/Linux | `~/.codeium/windsurf/mcp_config.json`             |
| Windows     | `%USERPROFILE%\.codeium\windsurf\mcp_config.json` |

```json
{
  "mcpServers": {
    "jira": {
      "command": "/path/to/simple-jira-mcp/venv/bin/python",
      "args": ["-m", "src"],
      "cwd": "/path/to/simple-jira-mcp",
      "env": {
        "JIRA_CONFIG_JSON": "[{\"id\": \"work\", \"url\": \"https://your-domain.atlassian.net\", \"email\": \"your-email@example.com\", \"token\": \"your-api-token\"}]"
      }
    }
  }
}
```

Access via Windsurf Settings > Cascade > Plugins (MCP servers).

### VS Code with GitHub Copilot

Config file: `.vscode/mcp.json` (project-level)

```json
{
  "servers": {
    "jira": {
      "command": "/path/to/simple-jira-mcp/venv/bin/python",
      "args": ["-m", "src"],
      "cwd": "/path/to/simple-jira-mcp",
      "env": {
        "JIRA_CONFIG_JSON": "[{\"id\": \"work\", \"url\": \"https://your-domain.atlassian.net\", \"email\": \"your-email@example.com\", \"token\": \"your-api-token\"}]"
      }
    }
  }
}
```

Requires VS Code 1.102+ with GitHub Copilot. Use Agent Mode in Copilot Chat.

### Zed

Add to Zed `settings.json`:

```json
{
  "context_servers": {
    "jira": {
      "command": "/path/to/simple-jira-mcp/venv/bin/python",
      "args": ["-m", "src"],
      "env": {
        "JIRA_CONFIG_JSON": "[{\"id\": \"work\", \"url\": \"https://your-domain.atlassian.net\", \"email\": \"your-email@example.com\", \"token\": \"your-api-token\"}]"
      }
    }
  }
}
```

Note: Zed does not document a `cwd` key, so this snippet omits it. The server
still starts fine, but pass `output_dir` explicitly to `download_attachment` —
otherwise files land in whatever directory Zed launched the server from.

### Windows Notes

On Windows, use full paths with backslashes:

```json
{
  "command": "C:\\path\\to\\simple-jira-mcp\\venv\\Scripts\\python.exe",
  "cwd": "C:\\path\\to\\simple-jira-mcp"
}
```

## Available Tools

| Tool                  | Description                          |
|-----------------------|--------------------------------------|
| `list_configs`        | List available Jira configurations   |
| `search_issues`       | Search issues using JQL              |
| `get_issue`           | Get detailed issue information       |
| `create_issue`        | Create a new issue                   |
| `download_attachment` | Download an attachment from an issue |

## Usage Notes

- `list_configs`: Returns configs with `default` true for the first entry
  in `JIRA_CONFIG_JSON`, plus each config's effective `timeout`. It never
  returns an error — with no configs loaded it reports `{"configs": []}`
  rather than `CONFIG_NOT_FOUND`. The server exits at startup when
  `JIRA_CONFIG_JSON` is unset or empty, so a running server always has at
  least one config.
- `search_issues`: JQL must include at least one bounding filter (project,
  status, assignee, reporter, priority, type, key, id, or a
  created/updated/resolved clause) — any one of them satisfies the check, so
  a query need not be scoped to a project. Quote values that are JQL
  reserved words: `project = "ON"`, not `project = ON`.
  Semicolons and newlines are rejected. Supports cursor pagination with
  `next_page_token` and `is_last` (the Jira `/search/jql` endpoint returns
  no total count). The optional `fields` allowlist is forwarded to Jira and
  drives the response shape: each issue contains `key`, `url`, and only the
  requested fields. Default fields are summary, status, assignee, priority,
  updated, created, labels, issuetype.
- `get_issue`: `include_comments` and `include_attachments` toggle those
  sections. Descriptions and comments are plain text; attachments include
  `size_kb` and `mime_type`.
- `create_issue`: Summary max 255 characters; description is converted to
  ADF; optional `priority`, `labels`, and `assignee_account_id`.
- `download_attachment`: `output_dir` must exist when provided (defaults to
  the current working directory); files are saved to
  `<output_dir>/<issue_key>/` with sanitized filenames.

## Reference

See [API_REFERENCE.md](API_REFERENCE.md) for tool inputs/outputs, error codes,
and JQL patterns.

## Development

```bash
# Run all checks (lint, type check, tests)
./check.sh

# Run specific checks
./check.sh -l    # Linting only
./check.sh -m    # Type checking only
./check.sh -t    # Tests only
./check.sh -c    # Tests with coverage
./check.sh -f    # Auto-fix linting issues
./check.sh -a    # Explicitly run all checks
./check.sh -h    # Show help
```

## License

MIT License - see [LICENSE](LICENSE) for details.
