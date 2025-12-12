# Simple Jira MCP

A Model Context Protocol (MCP) server that provides Jira Cloud integration
for AI agents.

## Features

- Search issues using JQL (Jira Query Language)
- Retrieve issue details with comments and attachments
- Create new issues
- Download attachments
- Support for multiple Jira configurations

## Requirements

- Python 3.11+
- Jira Cloud account with API token

## Installation

```bash
git clone https://github.com/yourusername/simple-jira-mcp.git
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
    "token": "your-api-token"
  }
]'
```

Generate an API token at: <https://id.atlassian.com/manage-profile/security/api-tokens>

## AI Tool Integration

### Claude Desktop

| Platform | Config Path |
|----------|-------------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

```json
{
  "mcpServers": {
    "jira": {
      "command": "python",
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
      "command": "python",
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
      "command": "python",
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
command = "python"
args = ["-m", "src"]
cwd = "/path/to/simple-jira-mcp"

[mcp_servers.jira.env]
JIRA_CONFIG_JSON = '[{"id": "work", "url": "https://your-domain.atlassian.net", "email": "your-email@example.com", "token": "your-api-token"}]'
```

### Cursor

| Scope | Config Path |
|-------|-------------|
| Global | `~/.cursor/mcp.json` |
| Project | `.cursor/mcp.json` |

```json
{
  "mcpServers": {
    "jira": {
      "command": "python",
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

| Platform | Config Path |
|----------|-------------|
| macOS/Linux | `~/.codeium/windsurf/mcp_config.json` |
| Windows | `%USERPROFILE%\.codeium\windsurf\mcp_config.json` |

```json
{
  "mcpServers": {
    "jira": {
      "command": "python",
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
      "command": "python",
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
      "source": "custom",
      "command": "python",
      "args": ["-m", "src"],
      "env": {
        "JIRA_CONFIG_JSON": "[{\"id\": \"work\", \"url\": \"https://your-domain.atlassian.net\", \"email\": \"your-email@example.com\", \"token\": \"your-api-token\"}]"
      }
    }
  }
}
```

Note: Run Zed from the project folder or use the full path to the Python
executable in the venv.

### Windows Notes

On Windows, use full paths with backslashes:

```json
{
  "command": "C:\\path\\to\\simple-jira-mcp\\venv\\Scripts\\python.exe",
  "cwd": "C:\\path\\to\\simple-jira-mcp"
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `list_configs` | List available Jira configurations |
| `search_issues` | Search issues using JQL |
| `get_issue` | Get detailed issue information |
| `create_issue` | Create a new issue |
| `download_attachment` | Download an attachment from an issue |

## Usage Notes

- `list_configs`: Returns configs with `default` true for the first entry
  in `JIRA_CONFIG_JSON`.
- `search_issues`: JQL must include at least one bounding filter;
  semicolons and newlines are rejected. Supports cursor pagination with
  `next_page_token`. The `fields` allowlist is forwarded to Jira to limit
  fetched data, but responses stay normalized to key, summary, status,
  assignee, priority, issue_type, labels, created, updated, url.
- `get_issue`: `include_comments` and `include_attachments` toggle those
  sections. Descriptions and comments are plain text; attachments include
  `size_kb` and `mime_type`.
- `create_issue`: Summary max 255 characters; description is converted to
  ADF; optional `priority`, `labels`, and `assignee_account_id`.
- `download_attachment`: `output_dir` must exist when provided; files are
  saved to `<output_dir>/<issue_key>/` with sanitized filenames.

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
```

## License

MIT License - see [LICENSE](LICENSE) for details.
