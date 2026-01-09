"""
Notes client - Python wrapper for hestia-notes-cli.

Provides async interface to Apple Notes via AppleScript.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import List, Optional

from .models import Note, NoteFolder

logger = logging.getLogger(__name__)


class NotesError(Exception):
    """Notes operation error."""
    pass


class NotesClient:
    """Async client for Apple Notes operations."""

    def __init__(self, cli_path: str = "~/.hestia/bin/hestia-notes-cli"):
        self.cli_path = Path(cli_path).expanduser()

    async def _run_cli(
        self,
        args: List[str],
        stdin: Optional[str] = None,
        timeout: float = 30.0,
    ) -> dict:
        """Run CLI command and parse JSON response."""
        if not self.cli_path.exists():
            raise NotesError(f"CLI not found: {self.cli_path}")

        try:
            proc = await asyncio.create_subprocess_exec(
                str(self.cli_path),
                *args,
                stdin=asyncio.subprocess.PIPE if stdin else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(stdin.encode() if stdin else None),
                timeout=timeout,
            )

            stdout_str = stdout.decode().strip()
            stderr_str = stderr.decode().strip()

            if not stdout_str:
                raise NotesError(f"Empty response from CLI. stderr: {stderr_str}")

            try:
                result = json.loads(stdout_str)
            except json.JSONDecodeError as e:
                raise NotesError(f"Invalid JSON response: {stdout_str[:200]}") from e

            if not result.get("success"):
                error_msg = result.get("error", "Unknown error")
                raise NotesError(error_msg)

            return result

        except asyncio.TimeoutError:
            raise NotesError(f"CLI command timed out after {timeout}s")
        except FileNotFoundError:
            raise NotesError(f"CLI not found: {self.cli_path}")

    async def list_folders(self) -> List[NoteFolder]:
        """List all note folders."""
        result = await self._run_cli(["list-folders"])
        folders = result.get("data", {}).get("folders", [])
        return [NoteFolder.from_dict(f) for f in folders]

    async def list_notes(self, folder: Optional[str] = None) -> List[Note]:
        """
        List notes with optional folder filter.

        Args:
            folder: Filter by folder name
        """
        args = ["list-notes"]

        if folder:
            args.extend(["--folder", folder])

        result = await self._run_cli(args)
        notes = result.get("data", {}).get("notes", [])
        return [Note.from_dict(n) for n in notes]

    async def get_note(self, note_id: str) -> Note:
        """Get note details and content by ID."""
        result = await self._run_cli(["get-note", note_id])
        note_data = result.get("data", {}).get("note", {})
        return Note.from_dict(note_data)

    async def create_note(
        self,
        title: str,
        body: Optional[str] = None,
        folder: Optional[str] = None,
    ) -> Note:
        """
        Create a new note.

        Args:
            title: Note title
            body: Note content
            folder: Folder name (uses default if not specified)
        """
        note_data = {"title": title}

        if body:
            note_data["body"] = body
        if folder:
            note_data["folder"] = folder

        result = await self._run_cli(
            ["create-note"],
            stdin=json.dumps(note_data),
        )

        note_dict = result.get("data", {}).get("note", {})
        return Note.from_dict(note_dict)

    async def update_note(
        self,
        note_id: str,
        title: Optional[str] = None,
        body: Optional[str] = None,
    ) -> Note:
        """
        Update an existing note.

        Only specified fields will be updated.
        """
        update_data = {}

        if title is not None:
            update_data["title"] = title
        if body is not None:
            update_data["body"] = body

        if not update_data:
            raise NotesError("No fields to update")

        result = await self._run_cli(
            ["update-note", note_id],
            stdin=json.dumps(update_data),
        )

        note_dict = result.get("data", {}).get("note", {})
        return Note.from_dict(note_dict)

    async def delete_note(self, note_id: str) -> bool:
        """Delete a note by ID."""
        result = await self._run_cli(["delete-note", note_id])
        return result.get("data", {}).get("deleted", False)

    async def search_notes(self, query: str) -> List[Note]:
        """
        Search notes by title (case-insensitive).

        Note: This performs client-side filtering since AppleScript
        doesn't support efficient full-text search.
        """
        all_notes = await self.list_notes()
        query_lower = query.lower()
        return [n for n in all_notes if query_lower in n.title.lower()]

    async def get_notes_in_folder(self, folder: str) -> List[Note]:
        """Get all notes in a specific folder."""
        return await self.list_notes(folder=folder)
