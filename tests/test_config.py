"""Tests for configuration loading."""

import json
import os

import pytest

from src.config import (
    get_config,
    get_default_config_id,
    load_configs,
    reset_config_state,
)


@pytest.fixture
def clean_config():
    """Reset config state before and after each test."""
    # Store original env var
    original = os.environ.get("JIRA_CONFIG_JSON")

    reset_config_state()

    yield

    # Restore original env var
    if original:
        os.environ["JIRA_CONFIG_JSON"] = original
    elif "JIRA_CONFIG_JSON" in os.environ:
        del os.environ["JIRA_CONFIG_JSON"]

    reset_config_state()


class TestLoadConfigs:
    def test_loads_single_config(self, clean_config):
        config_data = [
            {
                "id": "test",
                "url": "https://test.atlassian.net",
                "email": "test@example.com",
                "token": "test-token",
            }
        ]
        os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)

        configs = load_configs()

        assert len(configs) == 1
        assert configs[0].id == "test"
        assert configs[0].url == "https://test.atlassian.net"
        assert configs[0].email == "test@example.com"
        assert configs[0].token == "test-token"

    def test_loads_multiple_configs(self, clean_config):
        config_data = [
            {
                "id": "work",
                "url": "https://work.atlassian.net",
                "email": "work@example.com",
                "token": "work-token",
            },
            {
                "id": "personal",
                "url": "https://personal.atlassian.net",
                "email": "personal@example.com",
                "token": "personal-token",
            },
        ]
        os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)

        configs = load_configs()

        assert len(configs) == 2
        assert configs[0].id == "work"
        assert configs[1].id == "personal"

    def test_strips_trailing_slash_from_url(self, clean_config):
        config_data = [
            {
                "id": "test",
                "url": "https://test.atlassian.net/",
                "email": "test@example.com",
                "token": "test-token",
            }
        ]
        os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)

        configs = load_configs()

        assert configs[0].url == "https://test.atlassian.net"

    def test_raises_when_env_not_set(self, clean_config):
        if "JIRA_CONFIG_JSON" in os.environ:
            del os.environ["JIRA_CONFIG_JSON"]

        with pytest.raises(ValueError, match="not set"):
            load_configs()

    def test_raises_on_invalid_json(self, clean_config):
        os.environ["JIRA_CONFIG_JSON"] = "not valid json"

        with pytest.raises(ValueError, match="Invalid JSON"):
            load_configs()

    def test_raises_on_empty_array(self, clean_config):
        os.environ["JIRA_CONFIG_JSON"] = "[]"

        with pytest.raises(ValueError, match="non-empty array"):
            load_configs()

    def test_raises_on_non_array(self, clean_config):
        os.environ["JIRA_CONFIG_JSON"] = '{"id": "test"}'

        with pytest.raises(ValueError, match="non-empty array"):
            load_configs()

    def test_raises_on_missing_field(self, clean_config):
        config_data = [
            {
                "id": "test",
                "url": "https://test.atlassian.net",
                # missing email and token
            }
        ]
        os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)

        with pytest.raises(ValueError, match="Missing required field"):
            load_configs()


class TestGetConfig:
    def test_returns_config_by_id(self, clean_config):
        config_data = [
            {
                "id": "work",
                "url": "https://work.atlassian.net",
                "email": "work@example.com",
                "token": "work-token",
            },
            {
                "id": "personal",
                "url": "https://personal.atlassian.net",
                "email": "personal@example.com",
                "token": "personal-token",
            },
        ]
        os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)
        load_configs()

        config = get_config("personal")

        assert config is not None
        assert config.id == "personal"

    def test_returns_default_when_no_id(self, clean_config):
        config_data = [
            {
                "id": "first",
                "url": "https://first.atlassian.net",
                "email": "first@example.com",
                "token": "first-token",
            },
        ]
        os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)
        load_configs()

        config = get_config(None)

        assert config is not None
        assert config.id == "first"

    def test_returns_none_for_unknown_id(self, clean_config):
        config_data = [
            {
                "id": "test",
                "url": "https://test.atlassian.net",
                "email": "test@example.com",
                "token": "test-token",
            },
        ]
        os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)
        load_configs()

        config = get_config("nonexistent")

        assert config is None

    def test_returns_none_when_no_configs(self, clean_config):
        config = get_config()

        assert config is None


class TestGetDefaultConfigId:
    def test_returns_first_config_id(self, clean_config):
        config_data = [
            {
                "id": "first",
                "url": "https://first.atlassian.net",
                "email": "first@example.com",
                "token": "first-token",
            },
            {
                "id": "second",
                "url": "https://second.atlassian.net",
                "email": "second@example.com",
                "token": "second-token",
            },
        ]
        os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)
        load_configs()

        assert get_default_config_id() == "first"

    def test_returns_none_when_no_configs(self, clean_config):
        assert get_default_config_id() is None
