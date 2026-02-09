"""
Agent configuration loader for the .md-based config system.

Reads agent directories from disk, parses .md files into AgentConfig
objects, caches results, and supports hot-reload via file watching.

The config directory layout:
    {agents_root}/
    ├── tia/
    │   ├── IDENTITY.md
    │   ├── ANIMA.md
    │   ├── AGENT.md
    │   └── ...
    ├── mira/
    ├── olly/
    ├── .archived/          # Archived (deleted) agents
    └── .hestia-agents.yaml # Registry
"""

import re
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

from hestia.agents.config_models import (
    AgentConfig,
    AgentConfigFile,
    AgentIdentity,
    AgentRegistry,
    REQUIRED_FILES,
)
from hestia.agents.templates import (
    DEFAULT_AGENT_TEMPLATES,
    NEW_AGENT_TEMPLATE,
    LEGACY_SLOT_MAP,
)
from hestia.logging import get_logger, LogComponent

logger = get_logger()


# Default agents root for development (overridden for iCloud on production)
DEFAULT_AGENTS_ROOT = Path("data/agents")


class ConfigLoader:
    """
    Loads and caches agent configurations from .md file directories.

    Thread-safe via asyncio locks. Supports:
    - Eager or lazy loading of all config files
    - Cache invalidation per-agent or global
    - Validation of required files and content
    - Parsing of IDENTITY.md into AgentIdentity
    """

    def __init__(self, agents_root: Optional[Path] = None):
        """
        Initialize the config loader.

        Args:
            agents_root: Root directory containing agent subdirectories.
                         Defaults to data/agents/ for development.
        """
        self.agents_root = agents_root or DEFAULT_AGENTS_ROOT
        self._cache: Dict[str, AgentConfig] = {}
        self._registry: Optional[AgentRegistry] = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """
        Initialize the loader: ensure directories exist, scaffold defaults
        if needed, and load the registry.
        """
        async with self._lock:
            if self._initialized:
                return

            # Ensure root and archive directories exist
            self.agents_root.mkdir(parents=True, exist_ok=True)
            (self.agents_root / ".archived").mkdir(exist_ok=True)

            # Scaffold default agents if their directories don't exist
            for agent_name, templates in DEFAULT_AGENT_TEMPLATES.items():
                agent_dir = self.agents_root / agent_name
                if not agent_dir.exists():
                    logger.info(f"Scaffolding default agent: {agent_name}")
                    await self._scaffold_agent_directory(agent_name, templates, is_default=True)

            # Load or create registry
            self._registry = await self._load_registry()

            # Ensure all existing directories are in the registry
            await self._sync_registry()

            self._initialized = True
            logger.info(
                f"ConfigLoader initialized with {len(self._registry.agents)} agents "
                f"at {self.agents_root}"
            )

    async def _scaffold_agent_directory(
        self,
        agent_name: str,
        templates: Dict[AgentConfigFile, str],
        is_default: bool = False,
    ) -> Path:
        """
        Create an agent directory with template .md files.

        Args:
            agent_name: Directory name for the agent.
            templates: Dict mapping config files to template content.
            is_default: Whether this is a built-in default agent.

        Returns:
            Path to the created directory.
        """
        agent_dir = self.agents_root / agent_name
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Create memory subdirectory
        (agent_dir / "memory").mkdir(exist_ok=True)

        # Write template files
        for config_file, content in templates.items():
            if content:  # Don't write empty files
                file_path = agent_dir / config_file.value
                file_path.write_text(content, encoding="utf-8")

        # Write metadata
        meta = {
            "is_default": is_default,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "config_version": "1.0",
        }
        meta_path = agent_dir / ".agent-meta.yaml"
        meta_path.write_text(yaml.dump(meta, default_flow_style=False), encoding="utf-8")

        return agent_dir

    async def _load_registry(self) -> AgentRegistry:
        """Load or create the agent registry file."""
        registry_path = self.agents_root / ".hestia-agents.yaml"

        if registry_path.exists():
            try:
                data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
                if data:
                    return AgentRegistry.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to load registry, recreating: {e}")

        # Create default registry
        registry = AgentRegistry(
            default_agent="tia",
            agents=list(DEFAULT_AGENT_TEMPLATES.keys()),
        )
        await self._save_registry(registry)
        return registry

    async def _save_registry(self, registry: Optional[AgentRegistry] = None) -> None:
        """Save the registry to disk."""
        registry = registry or self._registry
        if not registry:
            return

        registry_path = self.agents_root / ".hestia-agents.yaml"
        registry.last_sync = datetime.now(timezone.utc)
        registry_path.write_text(
            yaml.dump(registry.to_dict(), default_flow_style=False),
            encoding="utf-8",
        )

    async def _sync_registry(self) -> None:
        """Ensure registry matches actual directories on disk."""
        if not self._registry:
            return

        # Find all agent directories (non-hidden, non-archived)
        existing_dirs = sorted([
            d.name for d in self.agents_root.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ])

        if set(existing_dirs) != set(self._registry.agents):
            self._registry.agents = existing_dirs
            await self._save_registry()

    # ─────────────────────────────────────────────
    # Loading
    # ─────────────────────────────────────────────

    async def load_agent(self, agent_name: str, force_reload: bool = False) -> Optional[AgentConfig]:
        """
        Load a single agent's configuration from disk.

        Args:
            agent_name: Directory name of the agent.
            force_reload: Skip cache and reload from disk.

        Returns:
            AgentConfig if found and valid, None otherwise.
        """
        if not force_reload and agent_name in self._cache:
            return self._cache[agent_name]

        agent_dir = self.agents_root / agent_name
        if not agent_dir.is_dir():
            return None

        try:
            config = await self._read_agent_directory(agent_dir)
            self._cache[agent_name] = config
            return config
        except Exception as e:
            logger.error(f"Failed to load agent '{agent_name}': {e}")
            return None

    async def _read_agent_directory(self, agent_dir: Path) -> AgentConfig:
        """
        Read all .md files from an agent directory into an AgentConfig.

        Args:
            agent_dir: Path to the agent directory.

        Returns:
            Populated AgentConfig.
        """
        dir_name = agent_dir.name

        # Read metadata
        meta = {}
        meta_path = agent_dir / ".agent-meta.yaml"
        if meta_path.exists():
            try:
                meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
            except Exception:
                pass

        # Read each config file
        file_contents = {}
        for config_file in AgentConfigFile:
            file_path = agent_dir / config_file.value
            if file_path.exists():
                try:
                    file_contents[config_file] = file_path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning(f"Failed to read {file_path}: {e}")
                    file_contents[config_file] = ""
            else:
                file_contents[config_file] = ""

        # Parse IDENTITY.md into structured data
        identity = self._parse_identity_md(
            file_contents.get(AgentConfigFile.IDENTITY, ""),
            dir_name,
        )

        # Get timestamps from metadata or file system
        created_at = datetime.fromisoformat(meta["created_at"]) if "created_at" in meta else datetime.now(timezone.utc)

        # Updated at = most recent file modification in the directory
        latest_mtime = max(
            (f.stat().st_mtime for f in agent_dir.iterdir() if f.is_file()),
            default=created_at.timestamp(),
        )
        updated_at = datetime.fromtimestamp(latest_mtime, tz=timezone.utc)

        config = AgentConfig(
            directory_name=dir_name,
            directory_path=agent_dir,
            config_version=meta.get("config_version", "1.0"),
            identity=identity,
            agent_md=file_contents.get(AgentConfigFile.AGENT, ""),
            anima_md=file_contents.get(AgentConfigFile.ANIMA, ""),
            user_md=file_contents.get(AgentConfigFile.USER, ""),
            tools_md=file_contents.get(AgentConfigFile.TOOLS, ""),
            heartbeat_md=file_contents.get(AgentConfigFile.HEARTBEAT, ""),
            boot_md=file_contents.get(AgentConfigFile.BOOT, ""),
            memory_md=file_contents.get(AgentConfigFile.MEMORY, ""),
            bootstrap_md=file_contents.get(AgentConfigFile.BOOTSTRAP, ""),
            is_default=meta.get("is_default", False),
            created_at=created_at,
            updated_at=updated_at,
        )
        config._files_loaded = True

        return config

    def _parse_identity_md(self, content: str, fallback_name: str) -> AgentIdentity:
        """
        Parse IDENTITY.md content into an AgentIdentity.

        Expected format:
            # AgentName
            **Full Name:** Hestia
            **Emoji:** 🔥
            **Vibe:** Efficient, sardonic
            **Gradient:** #E0A050 → #8B3A0F
            **Invoke:** `@tia\\b|@hestia\\b`
            **Temperature:** 0.0

        Args:
            content: Raw IDENTITY.md content.
            fallback_name: Name to use if parsing fails.

        Returns:
            Parsed AgentIdentity.
        """
        identity = AgentIdentity(name=fallback_name)

        if not content.strip():
            return identity

        # Parse name from first heading
        name_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if name_match:
            identity.name = name_match.group(1).strip()

        # Parse key-value fields
        field_patterns = {
            "full_name": r'\*\*Full Name:\*\*\s*(.+)',
            "emoji": r'\*\*Emoji:\*\*\s*(.+)',
            "vibe": r'\*\*Vibe:\*\*\s*(.+)',
            "avatar_path": r'\*\*Avatar:\*\*\s*(.+)',
            "invoke_pattern": r'\*\*Invoke:\*\*\s*`([^`]+)`',
            "temperature": r'\*\*Temperature:\*\*\s*([\d.]+)',
        }

        for field_name, pattern in field_patterns.items():
            match = re.search(pattern, content)
            if match:
                value = match.group(1).strip()
                if field_name == "temperature":
                    try:
                        setattr(identity, field_name, float(value))
                    except ValueError:
                        pass
                else:
                    setattr(identity, field_name, value)

        # Parse gradient (special format: #XXXXXX → #YYYYYY)
        gradient_match = re.search(
            r'\*\*Gradient:\*\*\s*#?([0-9A-Fa-f]{6})\s*→\s*#?([0-9A-Fa-f]{6})',
            content,
        )
        if gradient_match:
            identity.gradient_color_1 = gradient_match.group(1)
            identity.gradient_color_2 = gradient_match.group(2)

        return identity

    # ─────────────────────────────────────────────
    # Listing & Querying
    # ─────────────────────────────────────────────

    async def list_agents(self, include_archived: bool = False) -> List[AgentConfig]:
        """
        List all agent configurations.

        Args:
            include_archived: Whether to include archived agents.

        Returns:
            List of AgentConfig objects.
        """
        await self.initialize()

        agents = []
        for agent_name in self._registry.agents:
            config = await self.load_agent(agent_name)
            if config:
                agents.append(config)

        if include_archived:
            archived_dir = self.agents_root / ".archived"
            if archived_dir.exists():
                for d in sorted(archived_dir.iterdir()):
                    if d.is_dir():
                        config = await self._read_agent_directory(d)
                        config.is_archived = True
                        agents.append(config)

        return agents

    async def get_agent(self, agent_name: str) -> Optional[AgentConfig]:
        """
        Get a single agent by name.

        Args:
            agent_name: Directory name of the agent (e.g., "tia").

        Returns:
            AgentConfig if found, None otherwise.
        """
        await self.initialize()
        return await self.load_agent(agent_name)

    async def get_default_agent(self) -> Optional[AgentConfig]:
        """Get the default agent configuration."""
        await self.initialize()
        default_name = self._registry.default_agent if self._registry else "tia"
        return await self.get_agent(default_name)

    async def get_agent_by_mode(self, mode_value: str) -> Optional[AgentConfig]:
        """
        Get agent by legacy mode name (tia/mira/olly).

        For backward compatibility with the Mode enum system.
        """
        # Mode values are lowercase agent names
        return await self.get_agent(mode_value.lower())

    async def get_registry(self) -> AgentRegistry:
        """Get the current agent registry."""
        await self.initialize()
        return self._registry or AgentRegistry()

    # ─────────────────────────────────────────────
    # CRUD Operations
    # ─────────────────────────────────────────────

    async def create_agent(
        self,
        name: str,
        slug: Optional[str] = None,
    ) -> AgentConfig:
        """
        Create a new agent with template files.

        Args:
            name: Display name for the agent.
            slug: Directory name (auto-generated from name if not provided).

        Returns:
            The created AgentConfig.

        Raises:
            ValueError: If agent with this slug already exists.
        """
        await self.initialize()

        # Generate slug from name
        if not slug:
            slug = re.sub(r'[^a-z0-9_-]', '', name.lower().replace(' ', '-'))

        if not slug:
            raise ValueError("Agent name must contain at least one alphanumeric character")

        # Check for conflicts
        agent_dir = self.agents_root / slug
        if agent_dir.exists():
            raise ValueError(f"Agent '{slug}' already exists")

        # Format templates with agent name
        templates = {}
        for config_file, template in NEW_AGENT_TEMPLATE.items():
            templates[config_file] = template.format(name=name, slug=slug)

        await self._scaffold_agent_directory(slug, templates, is_default=False)

        # Update registry
        if self._registry:
            self._registry.agents.append(slug)
            await self._save_registry()

        # Load and cache
        config = await self.load_agent(slug, force_reload=True)
        if not config:
            raise RuntimeError(f"Failed to load newly created agent '{slug}'")

        logger.info(f"Created new agent: {name} ({slug})")
        return config

    async def archive_agent(self, agent_name: str) -> bool:
        """
        Archive (soft-delete) an agent by moving to .archived/.

        Args:
            agent_name: Directory name of the agent.

        Returns:
            True if archived, False if not found or is default.

        Raises:
            ValueError: If trying to archive a default agent's primary slot.
        """
        await self.initialize()

        # Prevent archiving the default agent
        if self._registry and agent_name == self._registry.default_agent:
            raise ValueError(f"Cannot archive the default agent '{agent_name}'")

        agent_dir = self.agents_root / agent_name
        if not agent_dir.exists():
            return False

        # Move to archived
        archived_dir = self.agents_root / ".archived"
        archived_dir.mkdir(exist_ok=True)

        # Add timestamp to avoid conflicts
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archived_path = archived_dir / f"{agent_name}_{timestamp}"
        agent_dir.rename(archived_path)

        # Update registry and cache
        if self._registry and agent_name in self._registry.agents:
            self._registry.agents.remove(agent_name)
            await self._save_registry()

        self._cache.pop(agent_name, None)

        logger.info(f"Archived agent: {agent_name} → {archived_path.name}")
        return True

    # ─────────────────────────────────────────────
    # Cache Management
    # ─────────────────────────────────────────────

    def invalidate_cache(self, agent_name: Optional[str] = None) -> None:
        """
        Invalidate cached configurations.

        Args:
            agent_name: Specific agent to invalidate, or None for all.
        """
        if agent_name:
            self._cache.pop(agent_name, None)
        else:
            self._cache.clear()

    async def reload_agent(self, agent_name: str) -> Optional[AgentConfig]:
        """Force-reload an agent from disk."""
        return await self.load_agent(agent_name, force_reload=True)

    async def reload_all(self) -> List[AgentConfig]:
        """Force-reload all agents from disk."""
        self._cache.clear()
        self._registry = await self._load_registry()
        await self._sync_registry()
        return await self.list_agents()


# ─────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────

_config_loader: Optional[ConfigLoader] = None


async def get_config_loader(agents_root: Optional[Path] = None) -> ConfigLoader:
    """Get or create the singleton ConfigLoader."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader(agents_root=agents_root)
        await _config_loader.initialize()
    return _config_loader


async def close_config_loader() -> None:
    """Clean up the config loader."""
    global _config_loader
    if _config_loader:
        _config_loader.invalidate_cache()
        _config_loader = None
