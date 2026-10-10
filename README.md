# Simple Jira MCP

A Model Context Protocol (MCP) server that provides Jira Cloud integration
for AI agents.

## Features

- Search issues using JQL (Jira Query Language)
- Retrieve issue details with comments and attachments
- Create, update, and delete issues
- List available transitions and transition issues with screen fields
- Add comments, including comments posted with a transition
- Download attachments
- Connect to multiple Jira instances

## Choosing this server

Use this server to run Jira tools locally with your API token:

- Connect to multiple Jira instances through `JIRA_CONFIG_JSON` and select
  one with `config_id`.
- Download attachments to disk.
- Search, read, create, update, delete, transition, and comment on issues
  through ten tools.
- Choose search response fields and read descriptions and comments as plain
  text.

You install and maintain the server. It supports Jira Cloud and uses the
configured API token for each instance. It does not support per-user OAuth
or other Atlassian products.

See [Atlassian's official MCP server](https://github.com/atlassian/atlassian-mcp-server)
for an alternative.

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

Set `timeout` per instance to limit each HTTP phase in seconds. It defaults
to 30 and must be positive. Raise it for slow connections. See
[API_REFERENCE.md](API_REFERENCE.md#timeouts) for details.

Use an `https://` URL to protect the API token in transit. Each entry must
have non-empty `id`, `url`, `email`, and `token` values. IDs must be unique.
The server refuses to start if any entry violates these rules.

## AI Tool Integration

In every snippet below, replace `/path/to/simple-jira-mcp` with your checkout
path. Set `command` to the venv interpreter created during installation.
Using a bare `python` requires the client to select an interpreter with the
server's dependencies installed.

Installation also creates a `venv/bin/simple-jira-mcp` script. You can use
its path as `command` with no `args` in place of the interpreter and
`-m simple_jira_mcp`.

When upgrading from 0.5.0 or earlier, change the module name in your client
config. Replace `"args": ["-m", "src"]` with
`"args": ["-m", "simple_jira_mcp"]` and rerun `pip install -e ".[dev]"`.

Set `cwd` to choose where `download_attachment` saves files when
`output_dir` is omitted. Without `cwd`, downloads use the directory from
which the client launched the server. The installed package can start
from any directory.

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
      "args": ["-m", "simple_jira_mcp"],
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
      "args": ["-m", "simple_jira_mcp"],
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
      "args": ["-m", "simple_jira_mcp"],
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
args = ["-m", "simple_jira_mcp"]
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
      "args": ["-m", "simple_jira_mcp"],
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
      "args": ["-m", "simple_jira_mcp"],
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
      "args": ["-m", "simple_jira_mcp"],
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
      "args": ["-m", "simple_jira_mcp"],
      "env": {
        "JIRA_CONFIG_JSON": "[{\"id\": \"work\", \"url\": \"https://your-domain.atlassian.net\", \"email\": \"your-email@example.com\", \"token\": \"your-api-token\"}]"
      }
    }
  }
}
```

Pass `output_dir` to `download_attachment` when using this snippet, which
omits `cwd`. Otherwise, downloads use the directory from which Zed launched
the server.

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
| `update_issue`        | Change fields on an issue            |
| `delete_issue`        | Permanently delete an issue          |
| `get_transitions`     | List transitions and screen fields   |
| `transition_issue`    | Transition an issue by ID or name    |
| `add_comment`         | Add a plain-text comment             |
| `download_attachment` | Download an attachment from an issue |

## Usage Notes

- `list_configs`: Returns each config's effective `timeout` and marks the
  first entry in `JIRA_CONFIG_JSON` with `default: true`. With no configs
  loaded, it returns `{"configs": []}`. It never returns an error. The server
  exits at startup when `JIRA_CONFIG_JSON` is unset or empty.
- `search_issues`: JQL must include at least one bounding filter (project,
  status, assignee, reporter, priority, type/issuetype, key, id, or a
  created/updated/resolved clause). Any one satisfies the check. A project
  filter is optional. Quote values that are JQL
  reserved words: `project = "ON"`, not `project = ON`.
  Semicolons and newlines are rejected. Supports cursor pagination with
  `next_page_token` and `is_last` (the Jira `/search/jql` endpoint returns
  no total count). The optional `fields` allowlist is forwarded to Jira and
  determines the response fields. Each issue contains `key`, `url`, and only
  the requested fields. Default fields are summary, status, assignee, priority,
  updated, created, labels, issuetype.
- `get_issue`: `include_comments` and `include_attachments` toggle those
  sections. Descriptions and comments are plain text; attachments include
  `size_kb` and `mime_type`.
- `create_issue`: Accepts a summary up to 255 characters and converts the
  description to ADF. `priority`, `labels`, and `assignee_account_id` are
  optional.
- `update_issue`: Omitted parameters stay unchanged. `labels` replaces the
  current labels. An empty `description` blanks the description. Other
  fields go in `fields` in Jira REST format, where a
  `null` value clears the field (`{"assignee": null}` unassigns). Status
  changes go through `transition_issue`.
- `delete_issue`: Permanently deletes the issue. Jira cannot restore it. An
  issue with
  subtasks is deleted only when `delete_subtasks` is true. The API token's
  user needs the Delete Issues permission in the project.
- `get_transitions`: Returns transition IDs, names, target statuses, and screen
  field metadata with required flags and allowed values.
- `transition_issue`: Accepts an ID or case-insensitive transition/target-status
  name. Ambiguous names return valid options. Optional `resolution` and `fields`
  must be accepted by the screen. An optional plain-text `comment` is posted
  in the same request when the screen accepts comments. Otherwise, it is
  posted immediately after the transition. Returns status, resolution, and
  `resolutiondate` from Jira.
  Jira sets `resolutiondate` itself; the API cannot edit it. Record the actual
  completion date in the comment.
- `add_comment`: Converts plain text to ADF and returns the comment ID and
  creation time.
- `download_attachment`: `output_dir` must exist when provided. It defaults
  to the current working directory. Files are saved to
  `<output_dir>/<issue_key>/` with sanitized filenames. If the filename is
  already taken, the attachment ID is appended (`log-10042.txt`).
- Errors: a failed call sets the MCP result's `isError` flag and carries
  `{"isError": true, "error": {"code": ..., "message": ...}}` as its content.

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
