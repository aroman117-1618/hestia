"""
Configuration management for Hestia CLI.

Manages ~/.hestia/config.yaml with server URL, preferences, and trust settings.
"""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml


DEFAULT_CONFIG: Dict[str, Any] = {
    "server": {
        "url": "https://localhost:8443",
        "verify_ssl": False,
    },
    "preferences": {
        "default_mode": "tia",
        "vi_mode": False,
        "show_metrics": True,
        "auto_context": True,
    },
    "trust": {
        "read": "auto",
        "write": "prompt",
        "execute": "prompt",
        "external": "prompt",
    },
}


def get_config_dir() -> Path:
    """Get or create ~/.hestia/ config directory."""
    config_dir = Path.home() / ".hestia"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get path to config file."""
    return get_config_dir() / "config.yaml"


def load_config() -> Dict[str, Any]:
    """Load config from disk, creating defaults if missing."""
    path = get_config_path()
    if path.exists():
        with open(path) as f:
            user_config = yaml.safe_load(f) or {}
        # Merge with defaults (user overrides take precedence)
        return _deep_merge(DEFAULT_CONFIG, user_config)
    else:
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)


def save_config(config: Dict[str, Any]) -> None:
    """Save config to disk."""
    path = get_config_path()
    with open(path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def get_server_url(config: Optional[Dict[str, Any]] = None) -> str:
    """Get server URL from config."""
    if config is None:
        config = load_config()
    return config.get("server", {}).get("url", DEFAULT_CONFIG["server"]["url"])


def get_verify_ssl(config: Optional[Dict[str, Any]] = None) -> bool:
    """Get SSL verification setting."""
    if config is None:
        config = load_config()
    return config.get("server", {}).get("verify_ssl", False)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dicts, override takes precedence."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
