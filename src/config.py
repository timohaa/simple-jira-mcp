"""Configuration loading for Jira MCP Server."""

import json
import logging
import os
import sys
from dataclasses import dataclass

# Configure logging to stderr only (critical for MCP stdio transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


@dataclass
class JiraConfig:
    """Configuration for a single Jira instance."""

    id: str
    url: str
    email: str
    token: str


_configs: list[JiraConfig] = []
_default_config_id: str | None = None


def load_configs() -> list[JiraConfig]:
    """Load Jira configurations from environment variable.

    Returns:
        List of JiraConfig instances.

    Raises:
        ValueError: If JIRA_CONFIG_JSON is not set or invalid.
    """
    global _configs, _default_config_id  # noqa: PLW0603

    config_json = os.environ.get("JIRA_CONFIG_JSON")
    if not config_json:
        msg = "JIRA_CONFIG_JSON environment variable not set"
        raise ValueError(msg)

    try:
        configs_data = json.loads(config_json)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON in JIRA_CONFIG_JSON: {e}"
        raise ValueError(msg) from e

    if not isinstance(configs_data, list) or not configs_data:
        msg = "JIRA_CONFIG_JSON must be a non-empty array"
        raise ValueError(msg)

    _configs = []
    for item in configs_data:
        if not isinstance(item, dict):
            msg = "Each config must be an object"
            raise ValueError(msg)

        required_fields = ["id", "url", "email", "token"]
        for field in required_fields:
            if field not in item:
                msg = f"Missing required field '{field}' in config"
                raise ValueError(msg)

        _configs.append(
            JiraConfig(
                id=str(item["id"]),
                url=str(item["url"]).rstrip("/"),
                email=str(item["email"]),
                token=str(item["token"]),
            )
        )

    _default_config_id = _configs[0].id if _configs else None
    logger.info("Loaded %d Jira configuration(s)", len(_configs))
    return _configs


def get_configs() -> list[JiraConfig]:
    """Get all loaded configurations.

    Returns:
        List of JiraConfig instances.
    """
    return _configs


def get_config(config_id: str | None = None) -> JiraConfig | None:
    """Get a specific configuration by ID.

    Args:
        config_id: The configuration ID. If None, returns the default config.

    Returns:
        JiraConfig if found, None otherwise.
    """
    target_id = config_id or _default_config_id
    if not target_id:
        return None

    for config in _configs:
        if config.id == target_id:
            return config
    return None


def get_default_config_id() -> str | None:
    """Get the default configuration ID.

    Returns:
        The default config ID, or None if no configs loaded.
    """
    return _default_config_id


def reset_config_state() -> None:
    """Testing helper to clear cached configuration state."""
    global _configs, _default_config_id  # noqa: PLW0603
    _configs = []
    _default_config_id = None
