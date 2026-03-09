"""Tests for config module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

from hestia_cli.config import (
    DEFAULT_CONFIG,
    _deep_merge,
    load_config,
    save_config,
    get_server_url,
    get_verify_ssl,
    validate_config,
)


class TestDeepMerge:
    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"server": {"url": "https://localhost:8443", "verify_ssl": False}}
        override = {"server": {"url": "https://custom:8443"}}
        result = _deep_merge(base, override)
        assert result["server"]["url"] == "https://custom:8443"
        assert result["server"]["verify_ssl"] is False

    def test_empty_override(self):
        base = {"a": 1}
        result = _deep_merge(base, {})
        assert result == {"a": 1}


class TestConfig:
    def test_load_creates_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            with patch('hestia_cli.config.get_config_path', return_value=config_path), \
                 patch('hestia_cli.config.get_config_dir', return_value=Path(tmpdir)):
                config = load_config()

            assert config["server"]["url"] == DEFAULT_CONFIG["server"]["url"]
            assert config_path.exists()

    def test_load_reads_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            custom = {"server": {"url": "https://custom:9999", "verify_ssl": True}}
            with open(config_path, "w") as f:
                yaml.dump(custom, f)

            with patch('hestia_cli.config.get_config_path', return_value=config_path):
                config = load_config()

            assert config["server"]["url"] == "https://custom:9999"
            assert config["server"]["verify_ssl"] is True
            # Default keys should still be present
            assert "preferences" in config

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            with patch('hestia_cli.config.get_config_path', return_value=config_path):
                save_config({"server": {"url": "https://test:1234"}})
                config = load_config()

            assert config["server"]["url"] == "https://test:1234"

    def test_get_server_url(self):
        config = {"server": {"url": "https://my-server:8443"}}
        assert get_server_url(config) == "https://my-server:8443"

    def test_get_server_url_default(self):
        assert get_server_url({}) == DEFAULT_CONFIG["server"]["url"]

    def test_get_verify_ssl(self):
        assert get_verify_ssl({"server": {"verify_ssl": True}}) is True
        assert get_verify_ssl({"server": {"verify_ssl": False}}) is False


class TestValidateConfig:
    """Tests for YAML config validation."""

    def test_valid_default_config_has_no_warnings(self):
        warnings = validate_config(DEFAULT_CONFIG)
        assert warnings == []

    def test_bad_server_url(self):
        config = {"server": {"url": "not-a-url"}}
        warnings = validate_config(config)
        assert any("http" in w for w in warnings)

    def test_invalid_default_mode(self):
        config = {"preferences": {"default_mode": "jarvis"}}
        warnings = validate_config(config)
        assert any("default_mode" in w for w in warnings)

    def test_valid_modes_pass(self):
        for mode in ("tia", "mira", "olly"):
            config = {"preferences": {"default_mode": mode}}
            warnings = validate_config(config)
            assert not any("default_mode" in w for w in warnings)

    def test_non_boolean_preference(self):
        config = {"preferences": {"show_metrics": "yes"}}
        warnings = validate_config(config)
        assert any("show_metrics" in w for w in warnings)

    def test_unknown_trust_tier(self):
        config = {"trust": {"admin": "auto"}}
        warnings = validate_config(config)
        assert any("admin" in w for w in warnings)

    def test_invalid_trust_level(self):
        config = {"trust": {"read": "always"}}
        warnings = validate_config(config)
        assert any("always" in w for w in warnings)

    def test_unknown_top_level_section(self):
        config = {"plugins": {"foo": "bar"}}
        warnings = validate_config(config)
        assert any("plugins" in w for w in warnings)
