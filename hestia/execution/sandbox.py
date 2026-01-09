"""
Sandbox runner for isolated tool execution.

Provides subprocess-based isolation with path allowlisting
and command blocking.
"""

import asyncio
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .models import SandboxConfig


class SandboxViolationError(Exception):
    """Raised when a sandbox policy is violated."""
    pass


class SandboxTimeoutError(Exception):
    """Raised when sandbox execution times out."""
    pass


class SandboxRunner:
    """
    Runs tool handlers with isolation and path restrictions.

    v1.0 uses subprocess-based isolation with allowlisting.
    Future versions may use Docker or macOS sandbox-exec.
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        """
        Initialize sandbox runner.

        Args:
            config: Sandbox configuration (uses defaults if not provided)
        """
        self.config = config or SandboxConfig()
        self._expanded_allowed_dirs: List[Path] = []
        self._expanded_write_dirs: List[Path] = []
        self._expand_paths()

    def _expand_paths(self) -> None:
        """Expand ~ in configured paths."""
        self._expanded_allowed_dirs = [
            Path(os.path.expanduser(p)).resolve()
            for p in self.config.allowed_directories
        ]
        self._expanded_write_dirs = [
            Path(os.path.expanduser(p)).resolve()
            for p in self.config.auto_approve_write_dirs
        ]

    def is_path_allowed(self, path: str, write: bool = False) -> bool:
        """
        Check if a path is allowed for access.

        Args:
            path: Path to check
            write: True if checking write access

        Returns:
            True if path is allowed
        """
        try:
            resolved = Path(os.path.expanduser(path)).resolve()
        except (ValueError, OSError):
            return False

        # Check against allowed directories
        for allowed_dir in self._expanded_allowed_dirs:
            try:
                resolved.relative_to(allowed_dir)
                return True
            except ValueError:
                continue

        return False

    def is_write_auto_approved(self, path: str) -> bool:
        """
        Check if a write to this path can be auto-approved.

        Args:
            path: Path to check

        Returns:
            True if write is auto-approved (no staging needed)
        """
        try:
            resolved = Path(os.path.expanduser(path)).resolve()
        except (ValueError, OSError):
            return False

        for approved_dir in self._expanded_write_dirs:
            try:
                resolved.relative_to(approved_dir)
                return True
            except ValueError:
                continue

        return False

    def is_command_blocked(self, command: str) -> bool:
        """
        Check if a command contains blocked patterns.

        Args:
            command: Command string to check

        Returns:
            True if command should be blocked
        """
        command_lower = command.lower()
        for blocked in self.config.blocked_commands:
            # Check for exact match or as part of command
            if blocked.lower() in command_lower:
                return True

        # Additional safety patterns
        dangerous_patterns = [
            r'\brm\s+-rf\s+/',        # rm -rf /
            r'\bsudo\b',              # sudo anything
            r'\bchmod\s+777\b',       # chmod 777
            r'>\s*/dev/',             # redirect to /dev
            r'\bdd\s+if=',            # dd commands
            r'\bmkfs\b',              # format commands
            r'\bshutdown\b',          # shutdown
            r'\breboot\b',            # reboot
            r'\|.*\bsh\b',            # pipe to shell
            r'\|.*\bbash\b',          # pipe to bash
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, command):
                return True

        return False

    def validate_path(self, path: str, write: bool = False) -> None:
        """
        Validate a path against sandbox policy.

        Args:
            path: Path to validate
            write: True if validating for write access

        Raises:
            SandboxViolationError: If path is not allowed
        """
        if not self.is_path_allowed(path, write):
            operation = "write to" if write else "access"
            raise SandboxViolationError(
                f"Sandbox violation: Not allowed to {operation} path: {path}"
            )

    def validate_command(self, command: str) -> None:
        """
        Validate a command against sandbox policy.

        Args:
            command: Command to validate

        Raises:
            SandboxViolationError: If command is blocked
        """
        if self.is_command_blocked(command):
            raise SandboxViolationError(
                f"Sandbox violation: Command contains blocked pattern"
            )

    async def run(
        self,
        handler: Callable[..., Any],
        args: Dict[str, Any],
        timeout: Optional[float] = None,
        allowed_paths: Optional[List[str]] = None,
    ) -> Any:
        """
        Execute a handler in the sandbox.

        Args:
            handler: Async function to execute
            args: Arguments to pass to handler
            timeout: Execution timeout (uses config default if not provided)
            allowed_paths: Additional allowed paths for this execution

        Returns:
            Handler result

        Raises:
            SandboxTimeoutError: If execution times out
            SandboxViolationError: If sandbox policy violated
        """
        if not self.config.enabled:
            # Sandbox disabled - execute directly
            if asyncio.iscoroutinefunction(handler):
                return await handler(**args)
            else:
                return handler(**args)

        effective_timeout = timeout or self.config.default_timeout
        effective_timeout = min(effective_timeout, self.config.max_timeout)

        # Add any additional allowed paths for this execution
        original_allowed = self._expanded_allowed_dirs.copy()
        if allowed_paths:
            for path in allowed_paths:
                expanded = Path(os.path.expanduser(path)).resolve()
                if expanded not in self._expanded_allowed_dirs:
                    self._expanded_allowed_dirs.append(expanded)

        try:
            # Execute with timeout
            if asyncio.iscoroutinefunction(handler):
                result = await asyncio.wait_for(
                    handler(**args),
                    timeout=effective_timeout
                )
            else:
                # Run sync handler in executor
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: handler(**args)),
                    timeout=effective_timeout
                )
            return result

        except asyncio.TimeoutError:
            raise SandboxTimeoutError(
                f"Execution timed out after {effective_timeout}s"
            )
        finally:
            # Restore original allowed paths
            self._expanded_allowed_dirs = original_allowed

    async def run_shell_command(
        self,
        command: str,
        working_dir: Optional[str] = None,
        timeout: Optional[float] = None,
        capture_output: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute a shell command in the sandbox.

        Args:
            command: Shell command to execute
            working_dir: Working directory (default: ~)
            timeout: Execution timeout
            capture_output: Whether to capture stdout/stderr

        Returns:
            Dict with returncode, stdout, stderr

        Raises:
            SandboxViolationError: If command is blocked
            SandboxTimeoutError: If execution times out
        """
        # Validate command
        self.validate_command(command)

        # Resolve working directory
        if working_dir:
            cwd = Path(os.path.expanduser(working_dir)).resolve()
            self.validate_path(str(cwd))
        else:
            cwd = Path.home()

        effective_timeout = timeout or self.config.default_timeout
        effective_timeout = min(effective_timeout, self.config.max_timeout)

        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_shell(
                    command,
                    cwd=cwd,
                    stdout=asyncio.subprocess.PIPE if capture_output else None,
                    stderr=asyncio.subprocess.PIPE if capture_output else None,
                ),
                timeout=5.0  # Timeout for process creation
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=effective_timeout
            )

            return {
                "returncode": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace") if stdout else "",
                "stderr": stderr.decode("utf-8", errors="replace") if stderr else "",
            }

        except asyncio.TimeoutError:
            # Try to kill the process
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            raise SandboxTimeoutError(
                f"Command execution timed out after {effective_timeout}s"
            )

    def get_expanded_allowed_dirs(self) -> List[str]:
        """Get list of expanded allowed directories."""
        return [str(p) for p in self._expanded_allowed_dirs]

    def get_expanded_write_dirs(self) -> List[str]:
        """Get list of expanded auto-approve write directories."""
        return [str(p) for p in self._expanded_write_dirs]


# Module-level singleton
_sandbox: Optional[SandboxRunner] = None


def get_sandbox_runner(config: Optional[SandboxConfig] = None) -> SandboxRunner:
    """
    Get the global sandbox runner singleton.

    Args:
        config: Optional config (only used on first call)

    Returns:
        Shared SandboxRunner instance
    """
    global _sandbox
    if _sandbox is None:
        _sandbox = SandboxRunner(config)
    return _sandbox
