"""
Configuration management for Hestia CLI.

Manages ~/.hestia/config.yaml with server URL, preferences, and trust settings.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


DEFAULT_CONFIG: Dict[str, Any] = {
    "server": {
        "url": "https://localhost:8443",
        "verify_ssl": False,
        "auto_start": True,
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


VALID_MODES = {"tia", "mira", "olly"}
VALID_TRUST_LEVELS = {"auto", "prompt"}
VALID_TRUST_TIERS = {"read", "write", "execute", "external"}


def validate_config(config: Dict[str, Any]) -> List[str]:
    """Validate config values, returning a list of warning messages.

    Checks:
    - server.url starts with http(s)://
    - preferences.default_mode is a valid agent name
    - preferences.show_metrics is a boolean
    - preferences.vi_mode is a boolean
    - trust tier keys are valid
    - trust tier levels are auto or prompt
    - No unknown top-level sections
    """
    warnings: List[str] = []

    # Check top-level sections
    known_sections = {"server", "preferences", "trust"}
    for key in config:
        if key not in known_sections:
            warnings.append(f"Unknown config section: '{key}'")

    # Validate server section
    server = config.get("server", {})
    if isinstance(server, dict):
        url = server.get("url", "")
        if url and not url.startswith(("http://", "https://")):
            warnings.append(f"server.url should start with http:// or https://, got: '{url}'")
    elif server is not None:
        warnings.append("server should be a mapping, not a scalar")

    # Validate preferences
    prefs = config.get("preferences", {})
    if isinstance(prefs, dict):
        mode = prefs.get("default_mode")
        if mode is not None and mode not in VALID_MODES:
            warnings.append(f"preferences.default_mode '{mode}' is not valid. Choose from: {', '.join(sorted(VALID_MODES))}")

        for bool_key in ("show_metrics", "vi_mode", "auto_context"):
            val = prefs.get(bool_key)
            if val is not None and not isinstance(val, bool):
                warnings.append(f"preferences.{bool_key} should be true/false, got: '{val}'")

    # Validate trust tiers
    trust = config.get("trust", {})
    if isinstance(trust, dict):
        for tier, level in trust.items():
            if tier not in VALID_TRUST_TIERS:
                warnings.append(f"Unknown trust tier: '{tier}'. Valid: {', '.join(sorted(VALID_TRUST_TIERS))}")
            elif level not in VALID_TRUST_LEVELS:
                warnings.append(f"trust.{tier} level '{level}' is not valid. Choose: {', '.join(sorted(VALID_TRUST_LEVELS))}")

    return warnings


def has_seen_banner() -> bool:
    """Check if the user has seen the animated startup banner."""
    return (get_config_dir() / "banner_seen").exists()


def mark_banner_seen() -> None:
    """Mark that the user has seen the animated startup banner."""
    (get_config_dir() / "banner_seen").touch()


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dicts, override takes precedence."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
