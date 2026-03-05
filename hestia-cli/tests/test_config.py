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
