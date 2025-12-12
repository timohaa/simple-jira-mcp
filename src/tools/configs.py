"""List configs tool implementation."""

from typing import Any

from src.config import get_configs, get_default_config_id


async def list_configs() -> dict[str, Any]:
    """List all configured Jira instances.

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
            }
            for config in configs
        ]
    }
