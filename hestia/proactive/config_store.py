"""
Config persistence for Proactive Intelligence.

Provides atomic file-based persistence for ProactiveConfig.
Ensures configuration survives restarts and crashes.

Security:
- Uses atomic writes to prevent corruption
- Validates JSON structure before loading
- Creates config directory with secure permissions
"""

import json
import os
from pathlib import Path
from typing import Optional

from hestia.logging import get_logger, LogComponent
from hestia.proactive.models import ProactiveConfig


logger = get_logger()

# Config file location
CONFIG_DIR = Path.home() / ".hestia"
CONFIG_FILE = CONFIG_DIR / "proactive_config.json"

# File permissions (owner read/write only)
CONFIG_FILE_MODE = 0o600
CONFIG_DIR_MODE = 0o700


def _ensure_config_dir() -> None:
    """
    Ensure config directory exists with secure permissions.

    Creates ~/.hestia with mode 700 (owner only).
    """
    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(mode=CONFIG_DIR_MODE, parents=True)
    else:
        # Ensure existing directory has correct permissions
        current_mode = CONFIG_DIR.stat().st_mode & 0o777
        if current_mode != CONFIG_DIR_MODE:
            os.chmod(CONFIG_DIR, CONFIG_DIR_MODE)


def load_config() -> ProactiveConfig:
    """
    Load proactive config from disk.

    Returns:
        ProactiveConfig loaded from file, or defaults if not found.
    """
    if not CONFIG_FILE.exists():
        logger.debug(
            "No proactive config file found, using defaults",
            component=LogComponent.ORCHESTRATION,
        )
        return ProactiveConfig()

    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)

        config = ProactiveConfig.from_dict(data)

        logger.info(
            "Loaded proactive config from disk",
            component=LogComponent.ORCHESTRATION,
            data={
                "policy": config.interruption_policy.value,
                "briefing_enabled": config.briefing_enabled,
            },
        )

        return config

    except json.JSONDecodeError as e:
        logger.warning(
            f"Invalid JSON in proactive config: {type(e).__name__}",
            component=LogComponent.ORCHESTRATION,
        )
        # Return defaults on parse error
        return ProactiveConfig()

    except Exception as e:
        logger.warning(
            f"Failed to load proactive config: {type(e).__name__}",
            component=LogComponent.ORCHESTRATION,
        )
        return ProactiveConfig()


def save_config(config: ProactiveConfig) -> bool:
    """
    Save proactive config to disk atomically.

    Uses atomic write pattern: write to temp file, then rename.
    This prevents corruption if crash occurs during write.

    Args:
        config: ProactiveConfig to persist.

    Returns:
        True if save succeeded, False otherwise.
    """
    try:
        _ensure_config_dir()

        # Convert to JSON
        data = config.to_dict()
        json_content = json.dumps(data, indent=2)

        # Write to temp file first
        temp_file = CONFIG_FILE.with_suffix(".tmp")

        with open(temp_file, "w") as f:
            f.write(json_content)

        # Set secure permissions on temp file
        os.chmod(temp_file, CONFIG_FILE_MODE)

        # Atomic rename (POSIX guarantees atomicity)
        temp_file.rename(CONFIG_FILE)

        logger.info(
            "Saved proactive config to disk",
            component=LogComponent.ORCHESTRATION,
            data={
                "policy": config.interruption_policy.value,
                "path": str(CONFIG_FILE),
            },
        )

        return True

    except Exception as e:
        logger.error(
            f"Failed to save proactive config: {type(e).__name__}",
            component=LogComponent.ORCHESTRATION,
        )
        # Clean up temp file if it exists
        temp_file = CONFIG_FILE.with_suffix(".tmp")
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass
        return False


def delete_config() -> bool:
    """
    Delete the proactive config file.

    Used for resetting to defaults or cleanup.

    Returns:
        True if deleted or didn't exist, False on error.
    """
    try:
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
            logger.info(
                "Deleted proactive config file",
                component=LogComponent.ORCHESTRATION,
            )
        return True
    except Exception as e:
        logger.error(
            f"Failed to delete proactive config: {type(e).__name__}",
            component=LogComponent.ORCHESTRATION,
        )
        return False


def config_exists() -> bool:
    """Check if a config file exists."""
    return CONFIG_FILE.exists()


def get_config_path() -> Path:
    """Get the path to the config file."""
    return CONFIG_FILE


# Singleton management
_config: Optional[ProactiveConfig] = None


def get_proactive_config() -> ProactiveConfig:
    """
    Get the current proactive config, loading from disk if needed.

    Returns cached config after first load for performance.
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def update_proactive_config(config: ProactiveConfig) -> bool:
    """
    Update the proactive config and persist to disk.

    Args:
        config: New configuration to save.

    Returns:
        True if save succeeded.
    """
    global _config
    if save_config(config):
        _config = config
        return True
    return False


def reset_proactive_config() -> ProactiveConfig:
    """
    Reset proactive config to defaults.

    Deletes the config file and returns new defaults.

    Returns:
        Fresh default ProactiveConfig.
    """
    global _config
    delete_config()
    _config = ProactiveConfig()
    return _config
