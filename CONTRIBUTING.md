# Contributing

Contributions are welcome. Please follow these guidelines.

## Development Setup

See `README.md` for installation instructions.

## Code Quality

All code must pass checks before submission:

```bash
./check.sh
```

This runs Ruff (linting), Mypy (type checking), and Pytest (tests).

## Guidelines

### Code Style

- Follow PEP 8 conventions
- Use type hints for all function parameters and returns
- Keep functions under 100 lines
- Keep files under 300 lines

### MCP Protocol

This is an MCP server using stdio transport. See `AGENTS.md` for critical rules.

### Testing

- Write tests for new functionality
- Maintain existing test coverage
- Use mocks for Jira API calls

### Commits

- Use clear, descriptive commit messages
- Reference issue numbers where applicable

## Pull Requests

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run `./check.sh` to verify all checks pass
5. Submit a pull request

## Reporting Issues

When reporting bugs, include:

- Python version
- Steps to reproduce
- Expected vs actual behavior
- Relevant error messages
