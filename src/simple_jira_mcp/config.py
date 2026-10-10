"""Configuration loading for Jira MCP Server."""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


DEFAULT_TIMEOUT = 30.0


REQUIRED_FIELDS = ("id", "url", "email", "token")


@dataclass(frozen=True)
class JiraConfig:
    """Configuration for a single Jira instance."""

    id: str
    url: str
    email: str
    token: str = field(repr=False)
    timeout: float = DEFAULT_TIMEOUT


_configs: list[JiraConfig] = []
_default_config_id: str | None = None


def _parse_timeout(item: dict[str, Any]) -> float:
    """Read the optional per-config 'timeout' field.

    Args:
        item: A single raw config object from JIRA_CONFIG_JSON.

    Returns:
        The timeout in seconds, or DEFAULT_TIMEOUT when the field is absent.

    Raises:
        ValueError: If the value is not a positive number.
    """
    if "timeout" not in item:
        return DEFAULT_TIMEOUT

    value = item["timeout"]
    # bool is a subclass of int, so `true` would otherwise become 1.0.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        msg = f"Config '{item['id']}' has invalid 'timeout': must be a number"
        raise ValueError(msg)

    if value <= 0:
        msg = f"Config '{item['id']}' has invalid 'timeout': must be positive"
        raise ValueError(msg)

    return float(value)


def _parse_config(item: object) -> JiraConfig:
    """Validate one raw config object from JIRA_CONFIG_JSON.

    Args:
        item: A single decoded element of the JIRA_CONFIG_JSON array.

    Returns:
        The validated configuration.

    Raises:
        ValueError: If a required field is missing or empty, or the URL is
            not https.
    """
    if not isinstance(item, dict):
        msg = "Each config must be an object"
        raise ValueError(msg)

    values: dict[str, str] = {}
    for name in REQUIRED_FIELDS:
        if name not in item:
            msg = f"Missing required field '{name}' in config"
            raise ValueError(msg)
        values[name] = str(item[name]).strip()
        if not values[name]:
            msg = f"Field '{name}' in config must not be empty"
            raise ValueError(msg)

    # Basic auth over plain http would send the API token in cleartext.
    if not values["url"].lower().startswith("https://"):
        msg = f"Config '{values['id']}' has invalid 'url': must start with https://"
        raise ValueError(msg)

    return JiraConfig(
        id=values["id"],
        url=values["url"].rstrip("/"),
        email=values["email"],
        token=values["token"],
        timeout=_parse_timeout(item),
    )


def load_configs() -> list[JiraConfig]:
    """Load Jira configurations from JIRA_CONFIG_JSON.

    Returns:
        List of JiraConfig instances.

    Raises:
        ValueError: If JIRA_CONFIG_JSON is not set or invalid, or two configs
            share an id.
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

    configs: list[JiraConfig] = []
    for item in configs_data:
        config = _parse_config(item)
        if any(existing.id == config.id for existing in configs):
            msg = f"Duplicate config id '{config.id}'"
            raise ValueError(msg)
        configs.append(config)

    _configs = configs
    _default_config_id = configs[0].id
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
    """Clear cached configuration state for tests."""
    global _configs, _default_config_id  # noqa: PLW0603
    _configs = []
    _default_config_id = None
