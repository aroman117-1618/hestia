#!/usr/bin/env python3
"""
Notion Sync Script — syncs git docs to Notion databases and reads the whiteboard.

Usage:
    python scripts/sync-notion.py read-whiteboard
    python scripts/sync-notion.py push [path]
    python scripts/sync-notion.py push --incremental
    python scripts/sync-notion.py status

Requires NOTION_TOKEN environment variable.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
RATE_LIMIT_DELAY = 0.34  # ~3 req/sec
MAX_BLOCKS_PER_REQUEST = 100

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYNC_STATE_PATH = PROJECT_ROOT / "data" / "notion-sync-state.json"
DOCS_ROOT = PROJECT_ROOT / "docs"

# Notion database/page IDs
DATABASES = {
    "archive": "feb292cc-621d-4982-942a-ea99dcf62e44",
    "sprints": "20e6158d-9d21-4e4d-be40-11e08f6932c3",
    "api_reference": "32e5d244-5f31-80e3-b67e-feff0575a3f2",
}
# Legacy — dynamic Sprints DB query replaces this in Task 3
WHITEBOARD_PAGE_ID = "e739da68-2b62-49ae-a4d1-979019771961"
API_REFERENCE_PAGE_ID = "3f49d829-d1aa-40be-89c0-f18cd5d3fd4e"  # Keep as fallback


# ---------------------------------------------------------------------------
# NotionClient
# ---------------------------------------------------------------------------

class NotionClient:
    """Thin httpx wrapper with auth, rate limiting, and retry."""

    def __init__(self, token: str) -> None:
        self._token = token
        self._client = httpx.Client(
            base_url=NOTION_API,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._last_request_time: float = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.monotonic()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        self._throttle()
        retries = 3
        for attempt in range(retries):
            resp = self._client.request(method, path, **kwargs)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 1.0))
                wait = retry_after * (2 ** attempt)
                print(f"  Rate limited, waiting {wait:.1f}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            if resp.status_code >= 400:
                error_body = resp.text[:500]
                raise RuntimeError(
                    f"Notion API error {resp.status_code} on {method} {path}: {error_body}"
                )
            return resp.json()
        raise RuntimeError(f"Notion API rate limit exceeded after {retries} retries")

    def get_blocks(self, block_id: str, page_size: int = 100) -> list[dict]:
        """Get all children blocks, handling pagination."""
        blocks: list[dict] = []
        cursor: Optional[str] = None
        while True:
            params: dict[str, Any] = {"page_size": page_size}
            if cursor:
                params["start_cursor"] = cursor
            data = self._request("GET", f"/blocks/{block_id}/children", params=params)
            blocks.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return blocks

    def create_page(self, parent: dict, properties: dict, children: Optional[list[dict]] = None) -> dict:
        body: dict[str, Any] = {"parent": parent, "properties": properties}
        if children:
            # Notion limits children on create to 100
            body["children"] = children[:MAX_BLOCKS_PER_REQUEST]
        result = self._request("POST", "/pages", json=body)
        # Append remaining blocks if needed
        if children and len(children) > MAX_BLOCKS_PER_REQUEST:
            page_id = result["id"]
            self._append_remaining_blocks(page_id, children[MAX_BLOCKS_PER_REQUEST:])
        return result

    def update_page(self, page_id: str, properties: dict) -> dict:
        return self._request("PATCH", f"/pages/{page_id}", json={"properties": properties})

    def replace_page_content(self, page_id: str, blocks: list[dict]) -> None:
        """Delete all existing blocks and replace with new ones."""
        existing = self.get_blocks(page_id)
        for block in existing:
            self._request("DELETE", f"/blocks/{block['id']}")
        self._append_remaining_blocks(page_id, blocks)

    def _append_remaining_blocks(self, page_id: str, blocks: list[dict]) -> None:
        for i in range(0, len(blocks), MAX_BLOCKS_PER_REQUEST):
            chunk = blocks[i:i + MAX_BLOCKS_PER_REQUEST]
            self._request("PATCH", f"/blocks/{page_id}/children", json={"children": chunk})

    def query_database(self, database_id: str, filter_obj: Optional[dict] = None) -> list[dict]:
        body: dict[str, Any] = {"page_size": 100}
        if filter_obj:
            body["filter"] = filter_obj
        results: list[dict] = []
        cursor: Optional[str] = None
        while True:
            if cursor:
                body["start_cursor"] = cursor
            data = self._request("POST", f"/databases/{database_id}/query", json=body)
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return results

    def search(self, query: str, filter_type: Optional[str] = None, page_size: int = 10) -> list[dict]:
        """Search the workspace for pages/databases by title."""
        body: dict[str, Any] = {"query": query, "page_size": page_size}
        if filter_type in ("page", "database"):
            body["filter"] = {"value": filter_type, "property": "object"}
        return self._request("POST", "/search", json=body).get("results", [])

    def get_page(self, page_id: str) -> dict:
        """Get page metadata (properties, parent, etc.)."""
        return self._request("GET", f"/pages/{page_id}")

    def get_database(self, database_id: str) -> dict:
        """Get database metadata (title, properties schema)."""
        return self._request("GET", f"/databases/{database_id}")

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# MarkdownToBlocks
# ---------------------------------------------------------------------------

class MarkdownToBlocks:
    """Convert markdown text to Notion block objects."""

    @staticmethod
    def convert(markdown: str) -> list[dict]:
        blocks: list[dict] = []
        lines = markdown.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            # Code block
            if line.startswith("```"):
                language = line[3:].strip() or "plain text"
                code_lines: list[str] = []
                i += 1
                while i < len(lines) and not lines[i].startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                i += 1  # skip closing ```
                code_content = "\n".join(code_lines)
                norm_lang = MarkdownToBlocks._normalize_language(language)
                # Chunk code blocks that exceed limit. Use 1900 to account for
                # multi-byte Unicode chars (Notion counts differently than Python len)
                chunk_size = 1900
                for chunk_start in range(0, max(len(code_content), 1), chunk_size):
                    chunk = code_content[chunk_start:chunk_start + chunk_size]
                    blocks.append({
                        "object": "block",
                        "type": "code",
                        "code": {
                            "rich_text": [{"type": "text", "text": {"content": chunk}}],
                            "language": norm_lang,
                        }
                    })
                continue

            # Headings
            if line.startswith("### "):
                blocks.append(MarkdownToBlocks._heading(line[4:], 3))
            elif line.startswith("## "):
                blocks.append(MarkdownToBlocks._heading(line[3:], 2))
            elif line.startswith("# "):
                blocks.append(MarkdownToBlocks._heading(line[2:], 1))
            # Horizontal rule
            elif line.strip() in ("---", "***", "___"):
                blocks.append({"object": "block", "type": "divider", "divider": {}})
            # Bullet list
            elif line.startswith("- ") or line.startswith("* "):
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": MarkdownToBlocks._parse_inline(line[2:])
                    }
                })
            # Numbered list
            elif re.match(r"^\d+\.\s", line):
                text = re.sub(r"^\d+\.\s", "", line)
                blocks.append({
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {
                        "rich_text": MarkdownToBlocks._parse_inline(text)
                    }
                })
            # Blockquote
            elif line.startswith("> "):
                blocks.append({
                    "object": "block",
                    "type": "quote",
                    "quote": {
                        "rich_text": MarkdownToBlocks._parse_inline(line[2:])
                    }
                })
            # Table (pipe-delimited)
            elif "|" in line and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1].strip()):
                table_lines = [line]
                i += 1
                # Skip separator row
                separator = lines[i]
                i += 1
                while i < len(lines) and lines[i].strip().startswith("|"):
                    table_lines.append(lines[i])
                    i += 1
                blocks.append(MarkdownToBlocks._build_table(table_lines))
                continue
            # Empty line — skip
            elif line.strip() == "":
                pass
            # Regular paragraph
            else:
                # Accumulate consecutive non-empty, non-special lines
                para_lines = [line]
                while (i + 1 < len(lines)
                       and lines[i + 1].strip()
                       and not lines[i + 1].startswith("#")
                       and not lines[i + 1].startswith("```")
                       and not lines[i + 1].startswith("- ")
                       and not lines[i + 1].startswith("* ")
                       and not lines[i + 1].startswith("> ")
                       and not re.match(r"^\d+\.\s", lines[i + 1])
                       and "|" not in lines[i + 1]):
                    i += 1
                    para_lines.append(lines[i])
                content = " ".join(para_lines)
                # Notion max 2000 chars per rich_text segment
                if content.strip():
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": MarkdownToBlocks._parse_inline(content[:1900])
                        }
                    })

            i += 1

        return blocks

    @staticmethod
    def _heading(text: str, level: int) -> dict:
        key = f"heading_{level}"
        return {
            "object": "block",
            "type": key,
            key: {"rich_text": MarkdownToBlocks._parse_inline(text)},
        }

    @staticmethod
    def _parse_inline(text: str) -> list[dict]:
        """Parse inline markdown (bold, italic, code, links) into Notion rich_text."""
        segments: list[dict] = []
        # Pattern: **bold**, *italic*, `code`, [text](url)
        pattern = re.compile(
            r"(\*\*(.+?)\*\*)"      # bold
            r"|(\*(.+?)\*)"          # italic
            r"|(`(.+?)`)"            # inline code
            r"|(\[(.+?)\]\((.+?)\))" # link
        )
        last_end = 0
        for m in pattern.finditer(text):
            # Plain text before this match
            if m.start() > last_end:
                plain = text[last_end:m.start()]
                if plain:
                    segments.append({"type": "text", "text": {"content": plain}})
            if m.group(2):  # bold
                segments.append({
                    "type": "text",
                    "text": {"content": m.group(2)},
                    "annotations": {"bold": True},
                })
            elif m.group(4):  # italic
                segments.append({
                    "type": "text",
                    "text": {"content": m.group(4)},
                    "annotations": {"italic": True},
                })
            elif m.group(6):  # code
                segments.append({
                    "type": "text",
                    "text": {"content": m.group(6)},
                    "annotations": {"code": True},
                })
            elif m.group(8):  # link
                url = m.group(9)
                # Only create link if URL looks valid (starts with http/https/mailto)
                if url.startswith(("http://", "https://", "mailto:")):
                    segments.append({
                        "type": "text",
                        "text": {"content": m.group(8), "link": {"url": url}},
                    })
                else:
                    # Render as plain text for relative/invalid URLs
                    segments.append({
                        "type": "text",
                        "text": {"content": f"{m.group(8)} ({url})"},
                    })
            last_end = m.end()
        # Remaining text
        if last_end < len(text):
            remaining = text[last_end:]
            if remaining:
                segments.append({"type": "text", "text": {"content": remaining}})
        if not segments:
            segments.append({"type": "text", "text": {"content": text}})
        return segments

    @staticmethod
    def _build_table(lines: list[str]) -> dict:
        """Build a Notion table block from pipe-delimited markdown lines."""
        rows: list[list[str]] = []
        for line in lines:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows.append(cells)
        if not rows:
            return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": ""}}]}}
        width = len(rows[0])
        table_rows = []
        for row in rows:
            # Pad or trim to consistent width
            cells = row[:width] + [""] * max(0, width - len(row))
            table_rows.append({
                "type": "table_row",
                "table_row": {
                    "cells": [[{"type": "text", "text": {"content": c}}] for c in cells]
                }
            })
        return {
            "object": "block",
            "type": "table",
            "table": {
                "table_width": width,
                "has_column_header": True,
                "has_row_header": False,
                "children": table_rows,
            }
        }

    # Notion's allowed code block languages
    ALLOWED_LANGUAGES = {
        "abap", "abc", "agda", "arduino", "ascii art", "assembly", "bash",
        "basic", "bnf", "c", "c#", "c++", "clojure", "coffeescript", "coq",
        "css", "dart", "dhall", "diff", "docker", "ebnf", "elixir", "elm",
        "erlang", "f#", "flow", "fortran", "gherkin", "glsl", "go", "graphql",
        "groovy", "haskell", "html", "idris", "java", "javascript", "json",
        "julia", "kotlin", "latex", "less", "lisp", "livescript", "llvm ir",
        "lua", "makefile", "markdown", "markup", "matlab", "mermaid", "nix",
        "objective-c", "ocaml", "pascal", "perl", "php", "plain text",
        "powershell", "prolog", "protobuf", "purescript", "python", "r",
        "racket", "reason", "ruby", "rust", "sass", "scala", "scheme",
        "scss", "shell", "solidity", "sql", "swift", "toml", "typescript",
        "vb.net", "verilog", "vhdl", "visual basic", "webassembly", "xml",
        "yaml", "java/c/c++/c#",
    }

    @staticmethod
    def _normalize_language(lang: str) -> str:
        mapping = {
            "py": "python", "js": "javascript", "ts": "typescript",
            "sh": "bash", "zsh": "bash", "yml": "yaml", "md": "markdown",
            "swift": "swift", "json": "json", "sql": "sql", "toml": "toml",
            "rust": "rust", "go": "go", "html": "html", "css": "css",
            "plain text": "plain text", "text": "plain text", "": "plain text",
            "dot": "plain text", "metal": "c", "objc": "objective-c",
            "tsx": "typescript", "jsx": "javascript", "svelte": "markup",
        }
        normalized = mapping.get(lang.lower(), lang.lower() if lang else "plain text")
        # If still not in allowed list, fall back to plain text
        if normalized not in MarkdownToBlocks.ALLOWED_LANGUAGES:
            return "plain text"
        return normalized


def _redact_tokens(text: str) -> str:
    """Strip JWT-shaped strings from text before pushing to Notion."""
    return re.sub(r'eyJ[A-Za-z0-9_-]{20,}\.{0,2}[A-Za-z0-9_.-]*', '<REDACTED_TOKEN>', text)


class ApiContractParser:
    """Parse api-contract.md into individual endpoint records."""

    MODULE_PATTERN = re.compile(r'^### (.+?) \((\d+) endpoints?\)', re.MULTILINE)
    ENDPOINT_PATTERN = re.compile(r'^#{3,4} (GET|POST|PUT|PATCH|DELETE) (/\S+)', re.MULTILINE)
    ERROR_CODE_PATTERN = re.compile(r'`(\d{3})`')
    NO_AUTH_PHRASES = ["no auth", "no auth required"]

    @staticmethod
    def parse(filepath: Path) -> list[dict]:
        """Parse api-contract.md into a list of endpoint dicts."""
        content = filepath.read_text(encoding="utf-8")
        content = _redact_tokens(content)
        endpoints: list[dict] = []

        # Find module sections
        module_matches = list(ApiContractParser.MODULE_PATTERN.finditer(content))
        # Find auth section endpoints (### level, before ## API Endpoints)
        auth_section_endpoints = list(re.finditer(
            r'^### (GET|POST|PUT|PATCH|DELETE) (/\S+)', content, re.MULTILINE
        ))

        api_section_start = content.find("## API Endpoints")

        # Parse auth section endpoints
        for match in auth_section_endpoints:
            if match.start() < api_section_start:
                method = match.group(1)
                path = match.group(2)
                next_heading = re.search(r'^###? ', content[match.end():], re.MULTILINE)
                end = match.end() + next_heading.start() if next_heading else len(content)
                body = content[match.end():end].strip()
                endpoints.append(ApiContractParser._build_endpoint(method, path, "Auth", body))

        # Parse module-grouped endpoints
        for i, mod_match in enumerate(module_matches):
            module_name = mod_match.group(1).split("(")[0].strip()
            mod_start = mod_match.end()
            mod_end = module_matches[i + 1].start() if i + 1 < len(module_matches) else len(content)
            mod_content = content[mod_start:mod_end]

            ep_matches = list(ApiContractParser.ENDPOINT_PATTERN.finditer(mod_content))
            for j, ep_match in enumerate(ep_matches):
                method = ep_match.group(1)
                path = ep_match.group(2)
                ep_start = ep_match.end()
                ep_end = ep_matches[j + 1].start() if j + 1 < len(ep_matches) else len(mod_content)
                body = mod_content[ep_start:ep_end].strip()
                endpoints.append(ApiContractParser._build_endpoint(method, path, module_name, body))

        return endpoints

    @staticmethod
    def _build_endpoint(method: str, path: str, module: str, body: str) -> dict:
        """Build an endpoint dict from parsed components."""
        lower_body = body.lower()

        auth_required = not any(phrase in lower_body for phrase in ApiContractParser.NO_AUTH_PHRASES)

        if "stub" in lower_body or "returns 501" in lower_body:
            status = "Stub"
        elif "deprecated" in lower_body:
            status = "Deprecated"
        else:
            status = "Active"

        errors_match = re.search(r'\*\*Errors.*?\*\*:?\s*(.+?)(?:\n|$)', body)
        response_codes: list[str] = ["200"]
        if errors_match:
            codes = ApiContractParser.ERROR_CODE_PATTERN.findall(errors_match.group(1))
            response_codes.extend(codes)
        if status == "Stub":
            response_codes.append("501")
        response_codes = sorted(set(response_codes))

        has_request_body = "**Request:**" in body and "```json" in body

        first_line = body.split("\n")[0].strip() if body else ""
        title = first_line if first_line and not first_line.startswith("**") and not first_line.startswith("```") else f"{method} {path}"

        return {
            "method": method,
            "path": path,
            "module": module,
            "title": title,
            "body": body,
            "auth_required": auth_required,
            "status": status,
            "response_codes": response_codes,
            "has_request_body": has_request_body,
        }


# ---------------------------------------------------------------------------
# SprintParser
# ---------------------------------------------------------------------------

class SprintParser:
    """Parse SPRINT.md into sprint records for Notion sync."""

    TABLE_ROW_PATTERN = re.compile(
        r'^\|\s*S?(\d+\.?\d*)\s*\|\s*(.+?)\s*\|\s*(\d+)h?\s*\|\s*(.+?)\s*\|',
        re.MULTILINE
    )

    SECTION_PATTERN = re.compile(
        r'^#{1,3}\s+(?:Sprint\s+|Current Sprint:\s*S?)(\d+\.?\d*)(.+)?$',
        re.MULTILINE
    )

    @staticmethod
    def parse(filepath: Path) -> list[dict]:
        """Parse SPRINT.md into a list of sprint dicts."""
        content = filepath.read_text(encoding="utf-8")
        sprints: list[dict] = []
        seen: set[str] = set()

        for match in SprintParser.TABLE_ROW_PATTERN.finditer(content):
            sprint_num = match.group(1)
            if sprint_num in seen:
                continue
            seen.add(sprint_num)

            scope = match.group(2).strip()
            hours_str = match.group(3).strip()
            status_raw = match.group(4).strip()

            sprints.append({
                "name": f"S{sprint_num}: {scope}",
                "sprint_number": sprint_num,
                "scope": scope,
                "hours_estimated": int(hours_str) if hours_str.isdigit() else None,
                "status": SprintParser._normalize_status(status_raw),
                "raw_status": status_raw,
            })

        for match in SprintParser.SECTION_PATTERN.finditer(content):
            sprint_num = match.group(1)
            if sprint_num in seen:
                continue
            seen.add(sprint_num)

            rest = (match.group(2) or "").strip().lstrip(":").strip()
            title = rest if rest else f"Sprint {sprint_num}"

            sprints.append({
                "name": f"S{sprint_num}: {title}",
                "sprint_number": sprint_num,
                "scope": title,
                "hours_estimated": None,
                "status": "Done",
                "raw_status": "COMPLETE",
            })

        return sprints

    @staticmethod
    def _normalize_status(raw: str) -> str:
        """Map raw status text to Notion status values."""
        lower = raw.lower()
        if "done" in lower or "complete" in lower or "live" in lower:
            return "Done"
        if "progress" in lower or "active" in lower:
            return "In Progress"
        if "block" in lower:
            return "Blocked"
        if "todo" in lower or "next" in lower:
            return "Next Up"
        if "defer" in lower or "future" in lower:
            return "Deferred"
        if "plan" in lower:
            return "Planning"
        return "Next Up"


# ---------------------------------------------------------------------------
# DocMapper
# ---------------------------------------------------------------------------

class DocMapper:
    """Map git file paths to Notion databases and extract properties."""

    # Path pattern → (database_key, type)
    # All docs route to archive with a Type tag
    ROUTING: list[tuple[str, str, Optional[str]]] = [
        ("docs/plans/", "archive", "Plan"),
        ("docs/discoveries/", "archive", "Discovery"),
        ("docs/audits/", "archive", "Audit"),
        ("docs/retrospectives/", "archive", "Retrospective"),
        ("docs/reference/", "archive", "Reference"),
        ("docs/architecture/", "archive", "Architecture"),
        ("docs/archive/", "archive", "Archive"),
        ("docs/hestia-security-architecture.md", "archive", "Security"),
        ("docs/hestia-development-plan.md", "archive", "Plan"),
        ("docs/metrics/", "archive", "Metrics"),
        ("docs/superpowers/plans/", "archive", "Plan"),
        ("docs/superpowers/specs/", "archive", "Spec"),
    ]

    @staticmethod
    def route(filepath: Path) -> Optional[tuple[str, Optional[str]]]:
        """Return (database_key, category) for a file path, or None if unmapped."""
        rel = str(filepath.relative_to(PROJECT_ROOT))
        for pattern, db_key, category in DocMapper.ROUTING:
            if rel.startswith(pattern) or rel == pattern:
                return (db_key, category)
        return None

    @staticmethod
    def extract_title(content: str, filepath: Path) -> str:
        """Extract title from first H1 or fallback to filename."""
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return filepath.stem.replace("-", " ").title()

    @staticmethod
    def extract_date(content: str, filepath: Path) -> Optional[str]:
        """Extract date from content metadata or filename."""
        # Try content patterns: **Date:** or Date:
        match = re.search(r"\*\*Date[:\*]*\*?\*?\s*:?\s*(\d{4}-\d{2}-\d{2})", content)
        if match:
            return match.group(1)
        # Try filename date prefix
        match = re.match(r"(\d{4}-\d{2}-\d{2})", filepath.name)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def extract_discovery_topics(content: str) -> list[str]:
        """Extract topic tags for discovery docs."""
        topics: list[str] = []
        lower = content[:1000].lower()
        keyword_map = {
            "trading": "Trading", "security": "Security", "ui": "UI/UX",
            "inference": "Inference", "memory": "Memory", "council": "Council",
            "workflow": "Workflows", "deployment": "Deployment", "health": "Health",
            "wiki": "Wiki", "research": "Research", "performance": "Performance",
        }
        for keyword, topic in keyword_map.items():
            if keyword in lower:
                topics.append(topic)
        return topics[:3]  # Notion multi_select limit is reasonable at 3

    @staticmethod
    def build_properties(filepath: Path, content: str, db_key: str, category: Optional[str]) -> dict:
        """Build Notion properties dict for a database entry."""
        title = DocMapper.extract_title(content, filepath)
        date = DocMapper.extract_date(content, filepath)
        rel_path = str(filepath.relative_to(PROJECT_ROOT))
        now = datetime.now(timezone.utc).isoformat()

        if db_key == "archive":
            props: dict[str, Any] = {
                "Title": {"title": [{"text": {"content": title}}]},
                "Git Path": {"rich_text": [{"text": {"content": rel_path}}]},
                "Last Synced": {"date": {"start": now}},
                "Status": {"select": {"name": "Active"}},
            }
            if category:
                props["Type"] = {"select": {"name": category}}
            if date:
                props["Date"] = {"date": {"start": date}}
            # Auto-detect topics
            topics = DocMapper.extract_discovery_topics(content)
            if topics:
                props["Domain/Topic"] = {"multi_select": [{"name": t} for t in topics]}
            return props

        # Fallback
        return {
            "Title": {"title": [{"text": {"content": title}}]},
            "Last Synced": {"date": {"start": now}},
        }


# ---------------------------------------------------------------------------
# SyncState
# ---------------------------------------------------------------------------

class SyncState:
    """Track sync state via content hashes in a JSON file."""

    def __init__(self, path: Path = SYNC_STATE_PATH) -> None:
        self._path = path
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self._path.exists():
            with open(self._path) as f:
                return json.load(f)
        return {"last_full_sync": None, "files": {}}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2)

    def content_hash(self, content: str) -> str:
        return f"sha256:{hashlib.sha256(content.encode()).hexdigest()[:16]}"

    def needs_sync(self, rel_path: str, content: str) -> bool:
        current_hash = self.content_hash(content)
        entry = self._data["files"].get(rel_path)
        if not entry:
            return True
        return entry.get("content_hash") != current_hash

    def record_sync(self, rel_path: str, content: str, notion_page_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._data["files"][rel_path] = {
            "content_hash": self.content_hash(content),
            "notion_page_id": notion_page_id,
            "last_synced": now,
        }

    def get_page_id(self, rel_path: str) -> Optional[str]:
        entry = self._data["files"].get(rel_path)
        return entry.get("notion_page_id") if entry else None

    def mark_full_sync(self) -> None:
        self._data["last_full_sync"] = datetime.now(timezone.utc).isoformat()

    @property
    def last_full_sync(self) -> Optional[str]:
        return self._data.get("last_full_sync")

    @property
    def file_count(self) -> int:
        return len(self._data.get("files", {}))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_read_whiteboard(client: NotionClient) -> None:
    """Read the Whiteboard card from the Sprints database."""
    db_id = DATABASES["sprints"]
    try:
        results = client.query_database(db_id, filter_obj={
            "and": [
                {"property": "Status", "status": {"equals": "Planning"}},
                {"property": "Title", "title": {"contains": "Whiteboard"}},
            ]
        })
    except Exception:
        results = []

    if results:
        page_id = results[0]["id"]
    else:
        # Fallback to legacy page ID
        print("(Whiteboard not found in Sprints DB — falling back to legacy page ID)", file=sys.stderr)
        page_id = WHITEBOARD_PAGE_ID

    blocks = client.get_blocks(page_id)
    if not blocks:
        print("(Whiteboard is empty)")
        return

    expanded = _expand_child_blocks(client, blocks)
    output = blocks_to_markdown(expanded)
    print(output)


def blocks_to_markdown(blocks: list[dict]) -> str:
    """Convert Notion blocks to readable markdown."""
    lines: list[str] = []
    for b in blocks:
        bt = b["type"]
        if bt in ("paragraph", "bulleted_list_item", "numbered_list_item",
                   "heading_1", "heading_2", "heading_3", "quote", "callout", "to_do"):
            rich_text = b.get(bt, {}).get("rich_text", [])
            text = "".join(r.get("plain_text", "") for r in rich_text)

            if bt == "heading_1":
                lines.append(f"# {text}")
            elif bt == "heading_2":
                lines.append(f"## {text}")
            elif bt == "heading_3":
                lines.append(f"### {text}")
            elif bt == "bulleted_list_item":
                lines.append(f"- {text}")
            elif bt == "numbered_list_item":
                lines.append(f"1. {text}")
            elif bt == "quote":
                lines.append(f"> {text}")
            elif bt == "to_do":
                checked = b.get("to_do", {}).get("checked", False)
                marker = "[x]" if checked else "[ ]"
                lines.append(f"- {marker} {text}")
            elif bt == "callout":
                icon = b.get("callout", {}).get("icon", {}).get("emoji", "")
                lines.append(f"> {icon} {text}")
            else:
                lines.append(text)
        elif bt == "divider":
            lines.append("---")
        elif bt == "code":
            lang = b.get("code", {}).get("language", "")
            code_text = "".join(r.get("plain_text", "") for r in b.get("code", {}).get("rich_text", []))
            lines.append(f"```{lang}")
            lines.append(code_text)
            lines.append("```")
        elif bt == "table":
            lines.append("[table]")
        elif bt == "toggle":
            rich_text = b.get("toggle", {}).get("rich_text", [])
            text = "".join(r.get("plain_text", "") for r in rich_text)
            lines.append(f"<details><summary>{text}</summary></details>")
        else:
            lines.append(f"[{bt}]")
    return "\n".join(lines)


def extract_property_value(prop: dict) -> str:
    """Extract a human-readable value from a Notion property object."""
    ptype = prop.get("type", "")

    if ptype == "title":
        return "".join(r.get("plain_text", "") for r in prop.get("title", []))
    elif ptype == "rich_text":
        return "".join(r.get("plain_text", "") for r in prop.get("rich_text", []))
    elif ptype == "number":
        val = prop.get("number")
        return str(val) if val is not None else ""
    elif ptype == "select":
        sel = prop.get("select")
        return sel["name"] if sel else ""
    elif ptype == "multi_select":
        return ", ".join(s["name"] for s in prop.get("multi_select", []))
    elif ptype == "status":
        st = prop.get("status")
        return st["name"] if st else ""
    elif ptype == "date":
        d = prop.get("date")
        if not d:
            return ""
        start = d.get("start", "")
        end = d.get("end", "")
        return f"{start} → {end}" if end else start
    elif ptype == "checkbox":
        return "Yes" if prop.get("checkbox") else "No"
    elif ptype == "url":
        return prop.get("url", "") or ""
    elif ptype == "email":
        return prop.get("email", "") or ""
    elif ptype == "phone_number":
        return prop.get("phone_number", "") or ""
    elif ptype == "people":
        return ", ".join(p.get("name", "Unknown") for p in prop.get("people", []))
    elif ptype == "relation":
        return f"[{len(prop.get('relation', []))} relations]"
    elif ptype == "rollup":
        rollup = prop.get("rollup", {})
        rtype = rollup.get("type", "")
        if rtype == "number":
            return str(rollup.get("number", ""))
        elif rtype == "array":
            return f"[{len(rollup.get('array', []))} items]"
        return f"[rollup:{rtype}]"
    elif ptype == "formula":
        formula = prop.get("formula", {})
        ftype = formula.get("type", "")
        return str(formula.get(ftype, ""))
    elif ptype == "created_time":
        return prop.get("created_time", "")
    elif ptype == "last_edited_time":
        return prop.get("last_edited_time", "")
    elif ptype == "created_by":
        return prop.get("created_by", {}).get("name", "")
    elif ptype == "last_edited_by":
        return prop.get("last_edited_by", {}).get("name", "")
    elif ptype == "files":
        files = prop.get("files", [])
        return ", ".join(f.get("name", "") for f in files) if files else ""
    else:
        return f"[{ptype}]"


def format_page_properties(properties: dict) -> str:
    """Format all properties of a Notion page as readable text."""
    lines: list[str] = []
    # Put title first
    for name, prop in sorted(properties.items()):
        if prop.get("type") == "title":
            lines.insert(0, f"**{name}**: {extract_property_value(prop)}")
        else:
            val = extract_property_value(prop)
            if val:
                lines.append(f"**{name}**: {val}")
    return "\n".join(lines)


def format_search_result(result: dict) -> str:
    """Format a search result (page or database) as a one-line summary."""
    obj_type = result.get("object", "")
    obj_id = result.get("id", "")

    if obj_type == "page":
        props = result.get("properties", {})
        # Find title property
        title = ""
        for prop in props.values():
            if prop.get("type") == "title":
                title = "".join(r.get("plain_text", "") for r in prop.get("title", []))
                break
        parent = result.get("parent", {})
        parent_type = parent.get("type", "")
        return f"[page] {title or '(untitled)'}  (id: {obj_id}, parent: {parent_type})"
    elif obj_type == "database":
        title_parts = result.get("title", [])
        title = "".join(r.get("plain_text", "") for r in title_parts)
        return f"[database] {title or '(untitled)'}  (id: {obj_id})"
    return f"[{obj_type}] (id: {obj_id})"


# ---------------------------------------------------------------------------
# Commands — Read
# ---------------------------------------------------------------------------

def cmd_search(client: NotionClient, query: str, filter_type: Optional[str], verbose: bool) -> None:
    """Search the workspace for pages or databases."""
    results = client.search(query, filter_type=filter_type)
    if not results:
        print(f"No results found for '{query}'")
        return

    print(f"Found {len(results)} result(s) for '{query}':\n")
    for i, r in enumerate(results, 1):
        print(f"  {i}. {format_search_result(r)}")
        if verbose:
            if r.get("object") == "page":
                props = r.get("properties", {})
                for name, prop in props.items():
                    val = extract_property_value(prop)
                    if val and prop.get("type") != "title":
                        print(f"       {name}: {val}")
            print()


def cmd_read_page(client: NotionClient, page_id: str, include_props: bool) -> None:
    """Read a page's properties and content."""
    # Normalize ID (accept with or without dashes)
    page_id = page_id.replace("-", "").strip()
    if len(page_id) == 32:
        page_id = f"{page_id[:8]}-{page_id[8:12]}-{page_id[12:16]}-{page_id[16:20]}-{page_id[20:]}"

    page = client.get_page(page_id)

    if include_props:
        props = page.get("properties", {})
        print("## Properties\n")
        print(format_page_properties(props))
        print("\n---\n")

    print("## Content\n")
    blocks = client.get_blocks(page_id)
    if blocks:
        # Recursively read child blocks for toggles and other containers
        expanded = _expand_child_blocks(client, blocks)
        print(blocks_to_markdown(expanded))
    else:
        print("(empty page)")


def cmd_update_page(client: NotionClient, page_id: str, markdown_file: Optional[str],
                     status: Optional[str]) -> None:
    """Update a page's content from a markdown file and/or update its status property."""
    # Normalize ID
    page_id = page_id.replace("-", "").strip()
    if len(page_id) == 32:
        page_id = f"{page_id[:8]}-{page_id[8:12]}-{page_id[12:16]}-{page_id[16:20]}-{page_id[20:]}"

    # Update properties (status)
    if status:
        # Detect property type (status vs select)
        page = client.get_page(page_id)
        props = page.get("properties", {})
        status_prop = None
        status_type = None
        for pname, pdef in props.items():
            if pdef.get("type") == "status":
                status_prop = pname
                status_type = "status"
                break
            elif pdef.get("type") == "select" and pname.lower() == "status":
                status_prop = pname
                status_type = "select"
                break
        if status_prop:
            if status_type == "status":
                client.update_page(page_id, {status_prop: {"status": {"name": status}}})
            else:
                client.update_page(page_id, {status_prop: {"select": {"name": status}}})
            print(f"Updated {status_prop} → {status}")

    # Update content from markdown file
    if markdown_file:
        filepath = Path(markdown_file)
        if not filepath.exists():
            # Try relative to project root
            filepath = PROJECT_ROOT / markdown_file
        if not filepath.exists():
            print(f"Error: File not found: {markdown_file}", file=sys.stderr)
            sys.exit(1)
        content = filepath.read_text(encoding="utf-8")
        blocks = MarkdownToBlocks.convert(content)
        client.replace_page_content(page_id, blocks)
        print(f"Updated page content from {filepath.name} ({len(blocks)} blocks)")

    if not status and not markdown_file:
        print("Nothing to update. Use --content <file> and/or --status <value>.")


def _expand_child_blocks(client: NotionClient, blocks: list[dict], depth: int = 0) -> list[dict]:
    """Recursively fetch child blocks for containers (toggles, synced blocks, etc.)."""
    if depth > 3:  # prevent infinite recursion
        return blocks
    expanded: list[dict] = []
    for b in blocks:
        expanded.append(b)
        if b.get("has_children", False):
            children = client.get_blocks(b["id"])
            if children:
                child_expanded = _expand_child_blocks(client, children, depth + 1)
                expanded.extend(child_expanded)
    return expanded


def cmd_query_db(client: NotionClient, db_name_or_id: str, text_filter: Optional[str],
                 status_filter: Optional[str], verbose: bool) -> None:
    """Query a database by name or ID, with optional filters."""
    # Resolve database ID
    db_id = DATABASES.get(db_name_or_id)
    if not db_id:
        # Try as raw ID
        if len(db_name_or_id.replace("-", "")) == 32:
            db_id = db_name_or_id
        else:
            # Search for it
            results = client.search(db_name_or_id, filter_type="database")
            if results:
                db_id = results[0]["id"]
                title = "".join(r.get("plain_text", "") for r in results[0].get("title", []))
                print(f"Resolved to database: {title} ({db_id})\n")
            else:
                print(f"Could not find database '{db_name_or_id}'")
                print(f"Known databases: {', '.join(DATABASES.keys())}")
                return

    # Build filter
    filter_obj: Optional[dict] = None
    filters: list[dict] = []

    if text_filter:
        # We don't know the title property name, so get schema first
        db_meta = client.get_database(db_id)
        db_props = db_meta.get("properties", {})
        title_prop = None
        for pname, pdef in db_props.items():
            if pdef.get("type") == "title":
                title_prop = pname
                break
        if title_prop:
            filters.append({
                "property": title_prop,
                "title": {"contains": text_filter},
            })

    if status_filter:
        db_meta = db_meta if "db_meta" in dir() else client.get_database(db_id)
        db_props = db_meta.get("properties", {})
        status_prop = None
        for pname, pdef in db_props.items():
            if pdef.get("type") == "status":
                status_prop = pname
                break
        if status_prop:
            filters.append({
                "property": status_prop,
                "status": {"equals": status_filter},
            })

    if len(filters) == 1:
        filter_obj = filters[0]
    elif len(filters) > 1:
        filter_obj = {"and": filters}

    results = client.query_database(db_id, filter_obj)
    if not results:
        print("No results found.")
        return

    print(f"Found {len(results)} item(s):\n")
    for i, page in enumerate(results, 1):
        props = page.get("properties", {})
        # Extract title
        title = ""
        for prop in props.values():
            if prop.get("type") == "title":
                title = "".join(r.get("plain_text", "") for r in prop.get("title", []))
                break
        page_id = page.get("id", "")
        print(f"  {i}. {title or '(untitled)'}  (id: {page_id})")

        if verbose:
            for name, prop in sorted(props.items()):
                val = extract_property_value(prop)
                if val and prop.get("type") != "title":
                    print(f"       {name}: {val}")
            print()


# ---------------------------------------------------------------------------
# Commands — Write / Push
# ---------------------------------------------------------------------------

def cmd_push(client: NotionClient, state: SyncState, target_path: Optional[str], force: bool, incremental: bool) -> None:
    """Push docs to Notion databases."""
    # Collect files to process
    files: list[Path] = []
    if target_path:
        target = PROJECT_ROOT / target_path
        if target.is_file() and target.suffix == ".md":
            files = [target]
        elif target.is_dir():
            files = sorted(target.rglob("*.md"))
        else:
            print(f"Error: {target_path} is not a markdown file or directory", file=sys.stderr)
            sys.exit(1)
    else:
        # Default: all docs/
        files = sorted(DOCS_ROOT.rglob("*.md"))

    # Skip non-routable files
    skipped = 0
    pushed = 0
    unchanged = 0
    errors = 0

    for filepath in files:
        rel_path = str(filepath.relative_to(PROJECT_ROOT))
        route = DocMapper.route(filepath)
        if not route:
            skipped += 1
            continue

        db_key, category = route
        content = filepath.read_text(encoding="utf-8")

        # Check if sync needed
        if not force and not state.needs_sync(rel_path, content):
            unchanged += 1
            continue

        # Skip the monolithic decision log and api-contract (special handling)
        if filepath.name == "hestia-decision-log.md":
            print(f"  [skip] {rel_path} (ADR decomposition not yet implemented)")
            skipped += 1
            continue
        if filepath.name == "api-contract.md":
            print(f"  [skip] {rel_path} (API decomposition not yet implemented)")
            skipped += 1
            continue

        # Build properties and blocks
        try:
            properties = DocMapper.build_properties(filepath, content, db_key, category)
            blocks = MarkdownToBlocks.convert(content)

            db_id = DATABASES[db_key]
            existing_page_id = state.get_page_id(rel_path)

            if existing_page_id:
                # Update existing page
                client.update_page(existing_page_id, properties)
                client.replace_page_content(existing_page_id, blocks)
                page_id = existing_page_id
                action = "updated"
            else:
                # Create new page
                result = client.create_page(
                    parent={"database_id": db_id},
                    properties=properties,
                    children=blocks,
                )
                page_id = result["id"]
                action = "created"

            state.record_sync(rel_path, content, page_id)
            pushed += 1
            print(f"  [{action}] {rel_path}")

        except Exception as e:
            errors += 1
            print(f"  [error] {rel_path}: {e}", file=sys.stderr)

    state.save()
    if not incremental:
        state.mark_full_sync()
        state.save()

    print(f"\nSync complete: {pushed} pushed, {unchanged} unchanged, {skipped} skipped, {errors} errors")


def cmd_status(state: SyncState) -> None:
    """Show sync status."""
    # Count total docs
    total_docs = len(list(DOCS_ROOT.rglob("*.md")))
    synced = state.file_count
    last_sync = state.last_full_sync or "never"

    print(f"Total docs:     {total_docs}")
    print(f"Synced:         {synced}")
    print(f"Unsynced:       {total_docs - synced}")
    print(f"Last full sync: {last_sync}")

    # Count stale (changed since last sync)
    stale = 0
    for filepath in DOCS_ROOT.rglob("*.md"):
        rel_path = str(filepath.relative_to(PROJECT_ROOT))
        content = filepath.read_text(encoding="utf-8")
        if state.needs_sync(rel_path, content):
            stale += 1
    print(f"Stale (need sync): {stale}")


def cmd_push_adrs(client: NotionClient, state: SyncState) -> None:
    """Parse hestia-decision-log.md and push/update individual ADRs."""
    decision_log = PROJECT_ROOT / "docs" / "hestia-decision-log.md"
    if not decision_log.exists():
        print("Error: docs/hestia-decision-log.md not found", file=sys.stderr)
        return

    content = decision_log.read_text(encoding="utf-8")
    adr_pattern = re.compile(r'^### (ADR-(\d+):\s*(.+))$', re.MULTILINE)
    matches = list(adr_pattern.finditer(content))

    domain_keywords = {
        "Inference": ["model", "inference", "ollama", "qwen", "llm", "cloud", "routing"],
        "Memory": ["memory", "chromadb", "vector", "chunk", "consolidat", "prun"],
        "Security": ["security", "auth", "credential", "keychain", "encrypt", "jwt"],
        "Architecture": ["architecture", "module", "pattern", "config", "startup"],
        "Council": ["council", "intent", "slm", "bypass"],
        "UI": ["ui", "swiftui", "ios", "macos", "frontend"],
        "Trading": ["trading", "bot", "exchange", "coinbase", "strategy"],
        "Orchestration": ["orchestrat", "agent", "handler", "workflow"],
        "API": ["api", "endpoint", "route", "rest"],
    }

    db_id = DATABASES["archive"]
    created = 0
    updated = 0
    unchanged = 0
    errors = 0

    for i, match in enumerate(matches):
        adr_num = int(match.group(2))
        title = match.group(3).strip()
        full_title = f"ADR-{adr_num:03d}: {title}"

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        adr_content = re.sub(r'\n---\s*$', '', content[start:end].strip())

        # Check hash
        adr_key = f"adr:{adr_num:03d}"
        if not state.needs_sync(adr_key, adr_content):
            unchanged += 1
            continue

        # Extract metadata
        date_match = re.search(r'\*\*Date\*\*:\s*(\d{4}-\d{2}-\d{2})', adr_content)
        date = date_match.group(1) if date_match else None

        status_match = re.search(r'\*\*Status\*\*:\s*(.+?)(?:\n|$)', adr_content)
        raw_status = status_match.group(1).strip() if status_match else "Accepted"
        if "deprecated" in raw_status.lower():
            status = "Deprecated"
        elif "superseded" in raw_status.lower():
            status = "Superseded"
        elif "proposed" in raw_status.lower():
            status = "Proposed"
        else:
            status = "Accepted"

        lower_text = (full_title + " " + adr_content)[:1000].lower()
        domains = [d for d, kws in domain_keywords.items() if any(k in lower_text for k in kws)][:3]

        now = datetime.now(timezone.utc).isoformat()
        props = {
            "Title": {"title": [{"text": {"content": full_title}}]},
            "ADR Number": {"number": adr_num},
            "Status": {"select": {"name": status}},
            "Last Synced": {"date": {"start": now}},
            "Type": {"select": {"name": "ADR"}},
        }
        if date:
            props["Date"] = {"date": {"start": date}}
        if domains:
            props["Domain/Topic"] = {"multi_select": [{"name": d} for d in domains]}

        blocks = MarkdownToBlocks.convert(adr_content)

        try:
            existing_page_id = state.get_page_id(adr_key)
            if existing_page_id:
                client.update_page(existing_page_id, props)
                client.replace_page_content(existing_page_id, blocks)
                page_id = existing_page_id
                action = "updated"
                updated += 1
            else:
                result = client.create_page(
                    parent={"database_id": db_id},
                    properties=props,
                    children=blocks,
                )
                page_id = result["id"]
                action = "created"
                created += 1

            state.record_sync(adr_key, adr_content, page_id)
            print(f"  [{action}] {full_title}")
        except Exception as e:
            errors += 1
            print(f"  [error] {full_title}: {e}", file=sys.stderr)

    state.save()
    print(f"\nADR sync: {created} created, {updated} updated, {unchanged} unchanged, {errors} errors")


def cmd_push_api(client: NotionClient, state: SyncState, force: bool) -> None:
    """Parse api-contract.md and push endpoints to API Reference database."""
    api_contract = PROJECT_ROOT / "docs" / "api-contract.md"
    if not api_contract.exists():
        print("Error: docs/api-contract.md not found", file=sys.stderr)
        return

    full_content = api_contract.read_text(encoding="utf-8")
    if not force and not state.needs_sync("api-contract:full", full_content):
        print("API contract unchanged — skipping")
        return

    endpoints = ApiContractParser.parse(api_contract)
    print(f"Parsed {len(endpoints)} endpoints from api-contract.md")

    db_id = DATABASES["api_reference"]
    created = 0
    updated = 0
    errors = 0

    for ep in endpoints:
        sync_key = f"api:{ep['method']}:{ep['path']}"
        now = datetime.now(timezone.utc).isoformat()

        props = {
            "Title": {"title": [{"text": {"content": ep["title"][:100]}}]},
            "Method": {"select": {"name": ep["method"]}},
            "Path": {"rich_text": [{"text": {"content": ep["path"]}}]},
            "Module": {"select": {"name": ep["module"]}},
            "Auth Required": {"checkbox": ep["auth_required"]},
            "Status": {"select": {"name": ep["status"]}},
            "Response Codes": {"multi_select": [{"name": c} for c in ep["response_codes"]]},
            "Request Body": {"checkbox": ep["has_request_body"]},
            "Last Synced": {"date": {"start": now}},
        }

        blocks = MarkdownToBlocks.convert(ep["body"])

        try:
            existing_page_id = state.get_page_id(sync_key)
            if existing_page_id:
                client.update_page(existing_page_id, props)
                client.replace_page_content(existing_page_id, blocks)
                page_id = existing_page_id
                updated += 1
            else:
                result = client.create_page(
                    parent={"database_id": db_id},
                    properties=props,
                    children=blocks,
                )
                page_id = result["id"]
                created += 1

            state.record_sync(sync_key, ep["body"], page_id)
            print(f"  [{'updated' if existing_page_id else 'created'}] {ep['method']} {ep['path']}")
        except Exception as e:
            errors += 1
            print(f"  [error] {ep['method']} {ep['path']}: {e}", file=sys.stderr)

    state.record_sync("api-contract:full", full_content, "batch")
    state.save()
    print(f"\nAPI sync: {created} created, {updated} updated, {errors} errors")


def cmd_sync_sprints(client: NotionClient, state: SyncState, force: bool) -> None:
    """Sync SPRINT.md to the Sprints database in Notion."""
    sprint_file = PROJECT_ROOT / "SPRINT.md"
    if not sprint_file.exists():
        print("Error: SPRINT.md not found", file=sys.stderr)
        return

    content = sprint_file.read_text(encoding="utf-8")
    if not force and not state.needs_sync("SPRINT.md", content):
        print("SPRINT.md unchanged — skipping")
        return

    sprints = SprintParser.parse(sprint_file)
    print(f"Parsed {len(sprints)} sprints from SPRINT.md")

    db_id = DATABASES["sprints"]
    created = 0
    updated = 0
    errors = 0

    existing_cards = client.query_database(db_id)
    existing_by_title: dict[str, str] = {}
    for card in existing_cards:
        props = card.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                title = "".join(r.get("plain_text", "") for r in prop.get("title", []))
                existing_by_title[title.lower()] = card["id"]
                break

    for sprint in sprints:
        sync_key = f"sprint:{sprint['sprint_number']}"
        now = datetime.now(timezone.utc).isoformat()

        props: dict[str, Any] = {
            "Title": {"title": [{"text": {"content": sprint["name"]}}]},
            "Status": {"status": {"name": sprint["status"]}},
            "Last Synced": {"date": {"start": now}},
        }
        if sprint["hours_estimated"]:
            props["Hours Estimated"] = {"number": sprint["hours_estimated"]}

        try:
            existing_page_id = state.get_page_id(sync_key)
            if not existing_page_id:
                for title, page_id in existing_by_title.items():
                    if sprint["sprint_number"] in title or sprint["scope"].lower() in title:
                        existing_page_id = page_id
                        break

            if existing_page_id:
                client.update_page(existing_page_id, props)
                page_id = existing_page_id
                action = "updated"
                updated += 1
            else:
                result = client.create_page(
                    parent={"database_id": db_id},
                    properties=props,
                )
                page_id = result["id"]
                action = "created"
                created += 1

            state.record_sync(sync_key, sprint["raw_status"], page_id)
            print(f"  [{action}] {sprint['name']} → {sprint['status']}")
        except Exception as e:
            errors += 1
            print(f"  [error] {sprint['name']}: {e}", file=sys.stderr)

    state.record_sync("SPRINT.md", content, "batch")
    state.save()
    print(f"\nSprint sync: {created} created, {updated} updated, {errors} errors")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync git docs to Notion databases and read the whiteboard.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # read-whiteboard
    subparsers.add_parser("read-whiteboard", help="Read the Notion whiteboard")

    # push
    push_parser = subparsers.add_parser("push", help="Push docs to Notion")
    push_parser.add_argument("path", nargs="?", help="Specific file or directory to push")
    push_parser.add_argument("--force", action="store_true", help="Force push even if unchanged")
    push_parser.add_argument("--incremental", action="store_true", help="Only push changed files")

    # push-adrs
    subparsers.add_parser("push-adrs", help="Parse decision log and push ADRs to Notion")

    # push-api
    push_api_parser = subparsers.add_parser("push-api", help="Parse api-contract.md and push endpoints to Notion")
    push_api_parser.add_argument("--force", action="store_true", help="Force push even if unchanged")

    # sync-sprints
    sync_sprints_parser = subparsers.add_parser("sync-sprints", help="Sync SPRINT.md to Sprints database")
    sync_sprints_parser.add_argument("--force", action="store_true", help="Force sync even if unchanged")

    # status
    subparsers.add_parser("status", help="Show sync status")

    # search
    search_parser = subparsers.add_parser("search", help="Search Notion workspace")
    search_parser.add_argument("query", help="Search text")
    search_parser.add_argument("--type", choices=["page", "database"], help="Filter by object type")
    search_parser.add_argument("-v", "--verbose", action="store_true", help="Show properties")

    # read-page
    read_page_parser = subparsers.add_parser("read-page", help="Read a page by ID")
    read_page_parser.add_argument("page_id", help="Notion page ID (with or without dashes)")
    read_page_parser.add_argument("--no-props", action="store_true", help="Skip properties, show content only")

    # query-db
    query_db_parser = subparsers.add_parser("query-db", help="Query a database")
    query_db_parser.add_argument("database", help="Database name (sprints, archive, api_reference) or ID")
    query_db_parser.add_argument("--title", help="Filter by title contains")
    query_db_parser.add_argument("--status", help="Filter by status equals")
    query_db_parser.add_argument("-v", "--verbose", action="store_true", help="Show all properties")

    # update-page
    update_page_parser = subparsers.add_parser("update-page", help="Update a page's content and/or status")
    update_page_parser.add_argument("page_id", help="Notion page ID")
    update_page_parser.add_argument("--content", help="Markdown file to push as page content")
    update_page_parser.add_argument("--status", dest="page_status", help="Set status property value")

    args = parser.parse_args()

    # Validate token
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        print("Error: NOTION_TOKEN environment variable not set", file=sys.stderr)
        sys.exit(1)

    client = NotionClient(token)
    state = SyncState()

    try:
        if args.command == "read-whiteboard":
            cmd_read_whiteboard(client)
        elif args.command == "push":
            cmd_push(client, state, args.path, args.force, args.incremental)
        elif args.command == "push-adrs":
            cmd_push_adrs(client, state)
        elif args.command == "push-api":
            cmd_push_api(client, state, args.force)
        elif args.command == "sync-sprints":
            cmd_sync_sprints(client, state, args.force)
        elif args.command == "status":
            cmd_status(state)
        elif args.command == "search":
            cmd_search(client, args.query, args.type, args.verbose)
        elif args.command == "read-page":
            cmd_read_page(client, args.page_id, include_props=not args.no_props)
        elif args.command == "query-db":
            cmd_query_db(client, args.database, args.title, args.status, args.verbose)
        elif args.command == "update-page":
            cmd_update_page(client, args.page_id, args.content, args.page_status)
    finally:
        client.close()


if __name__ == "__main__":
    main()
