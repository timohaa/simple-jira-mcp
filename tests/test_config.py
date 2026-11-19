"""Tests for configuration loading."""

import json
import os
from dataclasses import FrozenInstanceError

import pytest

from simple_jira_mcp.config import (
    JiraConfig,
    get_config,
    get_default_config_id,
    load_configs,
)


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

    @pytest.mark.parametrize(
        "value,match",
        [
            ("not valid json", "Invalid JSON"),
            ("[]", "non-empty array"),
            ('{"id": "test"}', "non-empty array"),
        ],
        ids=["invalid-json", "empty-array", "non-array"],
    )
    def test_raises_on_bad_env_value(self, clean_config, value, match):
        os.environ["JIRA_CONFIG_JSON"] = value

        with pytest.raises(ValueError, match=match):
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


def _load(*overrides):
    """Load configs built from a valid base entry plus per-entry overrides."""
    base = {
        "id": "test",
        "url": "https://test.atlassian.net",
        "email": "test@example.com",
        "token": "test-token",
    }
    os.environ["JIRA_CONFIG_JSON"] = json.dumps([{**base, **o} for o in overrides])
    return load_configs()


class TestConfigValidation:
    @pytest.mark.parametrize(
        "url", ["http://test.atlassian.net", "ftp://x", "test.atlassian.net"]
    )
    def test_rejects_non_https_url(self, clean_config, url):
        with pytest.raises(ValueError, match="must start with https://"):
            _load({"url": url})

    def test_accepts_uppercase_scheme(self, clean_config):
        assert _load({"url": "HTTPS://test.atlassian.net/"})[0].url == (
            "HTTPS://test.atlassian.net"
        )

    @pytest.mark.parametrize("field", ["id", "url", "email", "token"])
    @pytest.mark.parametrize("value", ["", "   "])
    def test_rejects_empty_field(self, clean_config, field, value):
        with pytest.raises(ValueError, match=f"'{field}' in config must not be empty"):
            _load({field: value})

    def test_rejects_duplicate_ids(self, clean_config):
        with pytest.raises(ValueError, match="Duplicate config id 'test'"):
            _load({}, {"url": "https://other.atlassian.net"})

    def test_failed_load_keeps_previous_configs(self, clean_config):
        _load({"id": "first"})

        with pytest.raises(ValueError, match="Duplicate"):
            _load({}, {})

        assert get_default_config_id() == "first"

    def test_rejects_non_object_entry(self, clean_config):
        os.environ["JIRA_CONFIG_JSON"] = json.dumps(["nope"])
        with pytest.raises(ValueError, match="must be an object"):
            load_configs()


class TestJiraConfig:
    def test_repr_hides_token(self):
        config = JiraConfig(
            id="a", url="https://a.atlassian.net", email="e", token="s3cret"
        )

        assert "s3cret" not in repr(config)
        assert "s3cret" not in str(config)

    @pytest.mark.parametrize("field", ["id", "url", "email", "token", "timeout"])
    def test_is_immutable(self, field):
        config = JiraConfig(
            id="a", url="https://a.atlassian.net", email="e", token="s3cret"
        )

        with pytest.raises(FrozenInstanceError):
            setattr(config, field, "other")

        assert config == JiraConfig(
            id="a", url="https://a.atlassian.net", email="e", token="s3cret"
        )
