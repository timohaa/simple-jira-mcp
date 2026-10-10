"""List configs tool implementation."""

from typing import Any

from simple_jira_mcp.config import get_configs, get_default_config_id


async def list_configs() -> dict[str, Any]:
    """List all configured Jira instances.

    Return an empty list when no configurations are loaded. This tool never
    returns an error.

    Returns:
        Dictionary containing available configurations.
    """
    configs = get_configs()
    default_id = get_default_config_id()

    return {
        "configs": [
            {
                "id": config.id,
                "url": config.url,
                "default": config.id == default_id,
                "timeout": config.timeout,
            }
            for config in configs
        ]
    }
