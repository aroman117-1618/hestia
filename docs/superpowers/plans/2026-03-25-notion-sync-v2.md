# Notion Sync V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve `scripts/sync-notion.py` to consolidate 3 databases into Archive, add per-endpoint API Reference database, automate sprint sync, and wire `sync-all` into 5 Claude Code skills.

**Architecture:** Single-script evolution — add new commands and update existing routing/properties in `sync-notion.py`. No new files. Databases created manually in Notion first, then IDs updated in the script.

**Tech Stack:** Python 3.12, httpx, Notion REST API (2022-06-28), argparse CLI

**Spec:** `docs/superpowers/specs/2026-03-25-notion-sync-v2-design.md`

---

## Pre-Implementation: Notion Setup (Manual)

Before any code changes, Andrew needs to:

1. **Create API Reference database** in Notion under Hestia with these properties:
   - Title (title) — endpoint description
   - Method (select) — GET, POST, PUT, PATCH, DELETE
   - Path (rich_text)
   - Module (select) — Auth, Chat, Memory, Trading, etc.
   - Auth Required (checkbox)
   - Status (select) — Active, Stub, Deprecated
   - Response Codes (multi_select) — 200, 400, 401, 403, 404, 409, 429, 501
   - Request Body (checkbox)
   - Last Synced (date)

2. **Add properties to existing Archive database:**
   - ADR Number (number)
   - Type (select) — if not already present, add values: ADR, Plan, Discovery, Audit, Retrospective, Spec, Reference, Architecture, Security, Archive
   - Status (select) — Active, Accepted, Deprecated, Superseded
   - Domain/Topic (multi_select)
   - Linked Sprint (relation → Sprints database)
   - Superseded By (relation → self)

3. **Record the new API Reference database ID** — needed for Task 2.

---

### Task 1: Consolidate DATABASES dict and DocMapper routing

**Files:**
- Modify: `scripts/sync-notion.py:41-46` (DATABASES dict)
- Modify: `scripts/sync-notion.py:439-453` (DocMapper.ROUTING)
- Modify: `scripts/sync-notion.py:517-568` (DocMapper.build_properties)

- [ ] **Step 1: Update DATABASES dict**

Replace lines 41-48:

```python
DATABASES = {
    "archive": "feb292cc-621d-4982-942a-ea99dcf62e44",
    "sprints": "20e6158d-9d21-4e4d-be40-11e08f6932c3",
    "api_reference": "<API_REFERENCE_DB_ID>",  # Andrew fills after Notion setup
}
# Remove WHITEBOARD_PAGE_ID — now queried dynamically from Sprints DB
API_REFERENCE_PAGE_ID = "3f49d829-d1aa-40be-89c0-f18cd5d3fd4e"  # Keep as fallback
```

- [ ] **Step 2: Update DocMapper.ROUTING**

Replace the ROUTING list — all routes now point to `"archive"`:

```python
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
```

- [ ] **Step 3: Unify DocMapper.build_properties for archive**

Replace the `build_properties` method to handle all types in a single `archive` branch:

```python
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
```

- [ ] **Step 4: Update cmd_push_adrs to target archive with ADR-specific properties**

In `cmd_push_adrs()`, change the db_id lookup and add `Type` property:

```python
db_id = DATABASES["archive"]
```

And in the props dict (around line 1167), add:

```python
props = {
    "Title": {"title": [{"text": {"content": full_title}}]},
    "ADR Number": {"number": adr_num},
    "Type": {"select": {"name": "ADR"}},
    "Status": {"select": {"name": status}},
    "Last Synced": {"date": {"start": now}},
}
if date:
    props["Date"] = {"date": {"start": date}}
if domains:
    props["Domain/Topic"] = {"multi_select": [{"name": d} for d in domains]}
```

- [ ] **Step 5: Test the consolidation manually**

```bash
source .venv/bin/activate
# Verify status still works
python scripts/sync-notion.py status
# Push a single test doc
python scripts/sync-notion.py push docs/plans/ --force
# Push ADRs
python scripts/sync-notion.py push-adrs
```

Verify in Notion that records appear in the Archive database with correct Type tags.

- [ ] **Step 6: Commit**

```bash
git add scripts/sync-notion.py
git commit -m "feat(notion): consolidate planning_logs + adr_registry into archive database"
```

---

### Task 2: Add API Reference database support

**Files:**
- Modify: `scripts/sync-notion.py` — add `ApiContractParser` class and `cmd_push_api` function

- [ ] **Step 1: Add token redaction utility**

Add after the `MarkdownToBlocks` class (around line 430):

```python
def _redact_tokens(text: str) -> str:
    """Strip JWT-shaped strings from text before pushing to Notion."""
    return re.sub(r'eyJ[A-Za-z0-9_-]{20,}\.{0,2}[A-Za-z0-9_.-]*', '<REDACTED_TOKEN>', text)
```

- [ ] **Step 2: Add ApiContractParser class**

Add after `_redact_tokens`:

```python
class ApiContractParser:
    """Parse api-contract.md into individual endpoint records."""

    # Module header pattern: ### Module Name (N endpoints)
    MODULE_PATTERN = re.compile(r'^### (.+?) \((\d+) endpoints?\)', re.MULTILINE)
    # Endpoint header pattern: #### METHOD /path or ### METHOD /path
    ENDPOINT_PATTERN = re.compile(r'^#{3,4} (GET|POST|PUT|PATCH|DELETE) (/\S+)', re.MULTILINE)
    # Error codes pattern: **Errors:** `400` ... `429` ...
    ERROR_CODE_PATTERN = re.compile(r'`(\d{3})`')
    # No-auth indicators
    NO_AUTH_PHRASES = ["no auth", "no auth required"]

    @staticmethod
    def parse(filepath: Path) -> list[dict]:
        """Parse api-contract.md into a list of endpoint dicts."""
        content = filepath.read_text(encoding="utf-8")
        content = _redact_tokens(content)
        endpoints: list[dict] = []

        # Find all module sections
        module_matches = list(ApiContractParser.MODULE_PATTERN.finditer(content))
        # Also find auth section endpoints (### level)
        auth_section_endpoints = list(re.finditer(
            r'^### (GET|POST|PUT|PATCH|DELETE) (/\S+)', content, re.MULTILINE
        ))

        # Parse auth section endpoints (before "## API Endpoints")
        api_section_start = content.find("## API Endpoints")
        for match in auth_section_endpoints:
            if match.start() < api_section_start:
                method = match.group(1)
                path = match.group(2)
                # Find end of this endpoint section
                next_heading = re.search(r'^###? ', content[match.end():], re.MULTILINE)
                end = match.end() + next_heading.start() if next_heading else len(content)
                body = content[match.end():end].strip()

                endpoints.append(ApiContractParser._build_endpoint(
                    method, path, "Auth", body
                ))

        # Parse module-grouped endpoints
        for i, mod_match in enumerate(module_matches):
            module_name = mod_match.group(1).split("(")[0].strip()
            # Clean module name: "Health & Status" -> "Health & Status"
            mod_start = mod_match.end()
            mod_end = module_matches[i + 1].start() if i + 1 < len(module_matches) else len(content)
            mod_content = content[mod_start:mod_end]

            # Find endpoints within this module
            ep_matches = list(ApiContractParser.ENDPOINT_PATTERN.finditer(mod_content))
            for j, ep_match in enumerate(ep_matches):
                method = ep_match.group(1)
                path = ep_match.group(2)
                ep_start = ep_match.end()
                ep_end = ep_matches[j + 1].start() if j + 1 < len(ep_matches) else len(mod_content)
                body = mod_content[ep_start:ep_end].strip()

                endpoints.append(ApiContractParser._build_endpoint(
                    method, path, module_name, body
                ))

        return endpoints

    @staticmethod
    def _build_endpoint(method: str, path: str, module: str, body: str) -> dict:
        """Build an endpoint dict from parsed components."""
        lower_body = body.lower()

        # Auth detection
        auth_required = not any(phrase in lower_body for phrase in ApiContractParser.NO_AUTH_PHRASES)

        # Status detection
        if "stub" in lower_body or "returns 501" in lower_body:
            status = "Stub"
        elif "deprecated" in lower_body:
            status = "Deprecated"
        else:
            status = "Active"

        # Response codes
        errors_match = re.search(r'\*\*Errors.*?\*\*:?\s*(.+?)(?:\n|$)', body)
        response_codes: list[str] = ["200"]  # Default success code
        if errors_match:
            codes = ApiContractParser.ERROR_CODE_PATTERN.findall(errors_match.group(1))
            response_codes.extend(codes)
        if status == "Stub":
            response_codes.append("501")
        response_codes = sorted(set(response_codes))

        # Request body detection
        has_request_body = "**Request:**" in body and "```json" in body

        # Title: extract first line of description or derive from path
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
```

- [ ] **Step 3: Add cmd_push_api function**

Add after `cmd_push_adrs`:

```python
def cmd_push_api(client: NotionClient, state: SyncState, force: bool) -> None:
    """Parse api-contract.md and push endpoints to API Reference database."""
    api_contract = PROJECT_ROOT / "docs" / "api-contract.md"
    if not api_contract.exists():
        print("Error: docs/api-contract.md not found", file=sys.stderr)
        return

    # Check if file changed at all (skip full parse if unchanged)
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

            state.record_sync(sync_key, ep["body"], page_id)
            print(f"  [{action}] {ep['method']} {ep['path']}")
        except Exception as e:
            errors += 1
            print(f"  [error] {ep['method']} {ep['path']}: {e}", file=sys.stderr)

    # Record full file sync
    state.record_sync("api-contract:full", full_content, "batch")
    state.save()
    print(f"\nAPI sync: {created} created, {updated} updated, {errors} errors")
```

- [ ] **Step 4: Register push-api subcommand in main()**

Add after the `push-adrs` subparser:

```python
# push-api
push_api_parser = subparsers.add_parser("push-api", help="Parse api-contract.md and push endpoints to Notion")
push_api_parser.add_argument("--force", action="store_true", help="Force push even if unchanged")
```

And in the command dispatch:

```python
elif args.command == "push-api":
    cmd_push_api(client, state, args.force)
```

- [ ] **Step 5: Test push-api manually**

```bash
source .venv/bin/activate
python scripts/sync-notion.py push-api --force
```

Verify in Notion: API Reference database has ~129 rows with correct Method, Path, Module, Auth Required, Status, Response Codes, Request Body properties.

- [ ] **Step 6: Commit**

```bash
git add scripts/sync-notion.py
git commit -m "feat(notion): add per-endpoint API Reference database sync"
```

---

### Task 3: Dynamic whiteboard reading from Sprints database

**Files:**
- Modify: `scripts/sync-notion.py:631-638` (cmd_read_whiteboard)

- [ ] **Step 1: Update cmd_read_whiteboard to query Sprints DB**

Replace `cmd_read_whiteboard`:

```python
def cmd_read_whiteboard(client: NotionClient) -> None:
    """Read the Whiteboard card from the Sprints database."""
    # Query Sprints DB for the Whiteboard card (Status = Planning, Title contains Whiteboard)
    db_id = DATABASES["sprints"]
    try:
        results = client.query_database(db_id, filter_obj={
            "and": [
                {"property": "Status", "status": {"equals": "Planning"}},
                {"property": "Title", "title": {"contains": "Whiteboard"}},
            ]
        })
    except Exception:
        # Fallback: try the old hardcoded page ID
        results = []

    if results:
        page_id = results[0]["id"]
    elif hasattr(sys.modules[__name__], 'WHITEBOARD_PAGE_ID'):
        # Fallback to legacy page ID
        print("(Whiteboard not found in Sprints DB — falling back to legacy page ID)", file=sys.stderr)
        page_id = WHITEBOARD_PAGE_ID
    else:
        print("(No whiteboard found)")
        return

    blocks = client.get_blocks(page_id)
    if not blocks:
        print("(Whiteboard is empty)")
        return

    # Recursively expand child blocks (toggles, etc.)
    expanded = _expand_child_blocks(client, blocks)
    output = blocks_to_markdown(expanded)
    print(output)
```

- [ ] **Step 2: Keep WHITEBOARD_PAGE_ID as fallback constant**

Keep the constant defined (for backward compat) but add a comment:

```python
# Legacy fallback — whiteboard is now queried dynamically from Sprints DB
WHITEBOARD_PAGE_ID = "e739da68-2b62-49ae-a4d1-979019771961"
```

- [ ] **Step 3: Test whiteboard reading**

```bash
source .venv/bin/activate
python scripts/sync-notion.py read-whiteboard
```

Should output the Whiteboard card's body content (Phase 1, iOS, Chat UX, etc.) from the Sprints database.

- [ ] **Step 4: Commit**

```bash
git add scripts/sync-notion.py
git commit -m "feat(notion): read whiteboard dynamically from Sprints database"
```

---

### Task 4: Add sync-sprints command

**Files:**
- Modify: `scripts/sync-notion.py` — add `SprintParser` class and `cmd_sync_sprints` function

- [ ] **Step 1: Add SprintParser class**

Add after `ApiContractParser`:

```python
class SprintParser:
    """Parse SPRINT.md into sprint records for Notion sync."""

    # Sprint table row: | S27.5 | Infrastructure... | 8h | WS1 DONE... |
    TABLE_ROW_PATTERN = re.compile(
        r'^\|\s*S?(\d+\.?\d*)\s*\|\s*(.+?)\s*\|\s*(\d+)h?\s*\|\s*(.+?)\s*\|',
        re.MULTILINE
    )

    # Sprint section header: ## Sprint 17 Summary or # Current Sprint: S27.5
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

        # Parse table rows first (roadmap tables)
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

        # Parse section headers for additional sprints
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
                "status": "Done",  # Historical sprints in summary sections are done
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
```

- [ ] **Step 2: Add cmd_sync_sprints function**

```python
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

    # Get existing sprint cards for matching
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
            # Match by sync state first, then by title
            existing_page_id = state.get_page_id(sync_key)
            if not existing_page_id:
                # Try fuzzy title match
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
```

- [ ] **Step 3: Register sync-sprints subcommand in main()**

```python
# sync-sprints
sync_sprints_parser = subparsers.add_parser("sync-sprints", help="Sync SPRINT.md to Sprints database")
sync_sprints_parser.add_argument("--force", action="store_true", help="Force sync even if unchanged")
```

And in the dispatch:

```python
elif args.command == "sync-sprints":
    cmd_sync_sprints(client, state, args.force)
```

- [ ] **Step 4: Test sync-sprints**

```bash
source .venv/bin/activate
python scripts/sync-notion.py sync-sprints --force
```

Verify in Notion: Sprint cards created/updated with correct Status values.

- [ ] **Step 5: Commit**

```bash
git add scripts/sync-notion.py
git commit -m "feat(notion): add sync-sprints command — SPRINT.md to Notion board"
```

---

### Task 5: Add sync-all command

**Files:**
- Modify: `scripts/sync-notion.py` — add `cmd_sync_all` function

- [ ] **Step 1: Add cmd_sync_all function**

Add after `cmd_sync_sprints`:

```python
def cmd_sync_all(client: NotionClient, state: SyncState, force: bool) -> None:
    """Full reconciliation: Archive + ADRs + Sprints + API Reference."""
    print("=" * 60)
    print("Notion Sync — Full Reconciliation")
    print("=" * 60)

    print("\n[1/4] Pushing docs to Archive...")
    cmd_push(client, state, target_path=None, force=force, incremental=not force)

    print("\n[2/4] Pushing ADRs to Archive...")
    cmd_push_adrs(client, state)

    print("\n[3/4] Syncing SPRINT.md to Sprints board...")
    cmd_sync_sprints(client, state, force)

    print("\n[4/4] Syncing API Reference...")
    cmd_push_api(client, state, force)

    print("\n" + "=" * 60)
    print("Sync complete.")
    print("=" * 60)
```

- [ ] **Step 2: Register sync-all subcommand in main()**

```python
# sync-all
sync_all_parser = subparsers.add_parser("sync-all", help="Full reconciliation: Archive + Sprints + API Reference")
sync_all_parser.add_argument("--force", action="store_true", help="Force sync even if unchanged")
sync_all_parser.add_argument("--incremental", action="store_true", help="Only sync changed files (default)")
```

And in the dispatch:

```python
elif args.command == "sync-all":
    cmd_sync_all(client, state, args.force)
```

- [ ] **Step 3: Test sync-all**

```bash
source .venv/bin/activate
python scripts/sync-notion.py sync-all --incremental
```

Should run all 4 phases. Most things skipped (unchanged). Verify no errors.

- [ ] **Step 4: Commit**

```bash
git add scripts/sync-notion.py
git commit -m "feat(notion): add sync-all command for full reconciliation"
```

---

### Task 6: Add create-sprint-item command

**Files:**
- Modify: `scripts/sync-notion.py` — add `cmd_create_sprint_item` function

- [ ] **Step 1: Add cmd_create_sprint_item function**

```python
def cmd_create_sprint_item(client: NotionClient, state: SyncState,
                            title: str, plan_path: Optional[str]) -> None:
    """Create a Sprint card and optionally link it to an Archive record."""
    db_id = DATABASES["sprints"]
    now = datetime.now(timezone.utc).isoformat()

    # Create sprint card
    sprint_props: dict[str, Any] = {
        "Title": {"title": [{"text": {"content": title}}]},
        "Status": {"status": {"name": "Next Up"}},
        "Last Synced": {"date": {"start": now}},
    }

    result = client.create_page(parent={"database_id": db_id}, properties=sprint_props)
    sprint_page_id = result["id"]
    print(f"Created sprint card: {title} (id: {sprint_page_id})")

    # If a plan path is provided, push it to Archive and link
    if plan_path:
        plan_file = Path(plan_path)
        if not plan_file.is_absolute():
            plan_file = PROJECT_ROOT / plan_path
        if not plan_file.exists():
            print(f"Warning: Plan file not found: {plan_path}", file=sys.stderr)
            return

        content = plan_file.read_text(encoding="utf-8")
        rel_path = str(plan_file.relative_to(PROJECT_ROOT))
        properties = DocMapper.build_properties(plan_file, content, "archive", "Plan")
        # Add Linked Sprint relation
        properties["Linked Sprint"] = {"relation": [{"id": sprint_page_id}]}
        blocks = MarkdownToBlocks.convert(content)

        archive_result = client.create_page(
            parent={"database_id": DATABASES["archive"]},
            properties=properties,
            children=blocks,
        )
        archive_page_id = archive_result["id"]
        state.record_sync(rel_path, content, archive_page_id)
        state.save()
        print(f"Created archive record: {rel_path} (id: {archive_page_id})")
        print(f"Linked sprint card → archive record")
```

- [ ] **Step 2: Register create-sprint-item subcommand in main()**

```python
# create-sprint-item
create_sprint_parser = subparsers.add_parser("create-sprint-item", help="Create a Sprint card with optional plan link")
create_sprint_parser.add_argument("title", help="Sprint card title")
create_sprint_parser.add_argument("--plan", help="Path to plan doc to push to Archive and link")
```

And in the dispatch:

```python
elif args.command == "create-sprint-item":
    cmd_create_sprint_item(client, state, args.title, args.plan)
```

- [ ] **Step 3: Test create-sprint-item**

```bash
source .venv/bin/activate
python scripts/sync-notion.py create-sprint-item "Test Sprint Item" --plan docs/superpowers/plans/2026-03-25-notion-sync-v2.md
```

Verify in Notion: new Sprint card with "Next Up" status, linked Archive record.

Then delete the test item manually in Notion.

- [ ] **Step 4: Commit**

```bash
git add scripts/sync-notion.py
git commit -m "feat(notion): add create-sprint-item command with plan linking"
```

---

### Task 7: Add migrate command

**Files:**
- Modify: `scripts/sync-notion.py` — add `cmd_migrate` function

- [ ] **Step 1: Add cmd_migrate function**

```python
# Old database IDs for migration
_LEGACY_DATABASES = {
    "planning_logs": "32d5d244-5f31-813d-a693-db7821dbeb2e",
    "adr_registry": "5b0e4074-eca7-4d9c-be40-0e7486a7f362",
}


def cmd_migrate(client: NotionClient, state: SyncState, dry_run: bool) -> None:
    """One-time migration: move pages from planning_logs + adr_registry to consolidated archive."""
    archive_db_id = DATABASES["archive"]

    for old_name, old_db_id in _LEGACY_DATABASES.items():
        print(f"\n--- Migrating from {old_name} ({old_db_id}) ---")

        try:
            pages = client.query_database(old_db_id)
        except Exception as e:
            print(f"  [error] Could not query {old_name}: {e}", file=sys.stderr)
            continue

        print(f"  Found {len(pages)} pages")

        for page in pages:
            props = page.get("properties", {})
            # Extract title
            title = ""
            for prop in props.values():
                if prop.get("type") == "title":
                    title = "".join(r.get("plain_text", "") for r in prop.get("title", []))
                    break

            if dry_run:
                print(f"  [dry-run] Would migrate: {title}")
                continue

            # Read page content
            try:
                blocks = client.get_blocks(page["id"])
                expanded = _expand_child_blocks(client, blocks)
            except Exception:
                expanded = []

            # Determine type from old database
            if old_name == "adr_registry":
                type_tag = "ADR"
            else:
                # Try to preserve existing Type/Category
                type_val = extract_property_value(props.get("Type", {}))
                type_tag = type_val if type_val else "Plan"

            now = datetime.now(timezone.utc).isoformat()
            new_props: dict[str, Any] = {
                "Title": {"title": [{"text": {"content": title}}]},
                "Type": {"select": {"name": type_tag}},
                "Last Synced": {"date": {"start": now}},
                "Status": {"select": {"name": "Active"}},
            }

            # Carry over date if present
            date_val = props.get("Date", {})
            if date_val and date_val.get("date"):
                new_props["Date"] = date_val

            # Carry over ADR Number if present
            adr_num = props.get("ADR Number", {})
            if adr_num and adr_num.get("number") is not None:
                new_props["ADR Number"] = {"number": adr_num["number"]}

            # Carry over Domain/Topic or Topic
            for topic_key in ("Domain/Topic", "Topic", "Domain"):
                topic_val = props.get(topic_key, {})
                if topic_val and topic_val.get("multi_select"):
                    new_props["Domain/Topic"] = topic_val
                    break

            # Carry over Git Path
            git_path = props.get("Git Path", {})
            if git_path and git_path.get("rich_text"):
                new_props["Git Path"] = git_path

            # Carry over Status (for ADRs: Accepted/Deprecated/Superseded)
            status_val = props.get("Status", {})
            if status_val:
                sv = extract_property_value(status_val)
                if sv in ("Accepted", "Deprecated", "Superseded", "Proposed"):
                    new_props["Status"] = {"select": {"name": sv}}

            try:
                result = client.create_page(
                    parent={"database_id": archive_db_id},
                    properties=new_props,
                    children=expanded if expanded else None,
                )
                new_page_id = result["id"]

                # Update sync state if we have a git path
                git_path_text = extract_property_value(props.get("Git Path", {}))
                if git_path_text:
                    state.record_sync(git_path_text, title, new_page_id)

                print(f"  [migrated] {title} → {new_page_id}")
            except Exception as e:
                print(f"  [error] {title}: {e}", file=sys.stderr)

    if not dry_run:
        state.save()
        print("\nMigration complete. Manually archive the old databases in Notion.")
    else:
        print("\nDry run complete. Run without --dry-run to execute.")
```

- [ ] **Step 2: Register migrate subcommand in main()**

```python
# migrate
migrate_parser = subparsers.add_parser("migrate", help="One-time migration from old databases to Archive")
migrate_parser.add_argument("--dry-run", action="store_true", help="Preview migration without making changes")
```

And in the dispatch:

```python
elif args.command == "migrate":
    cmd_migrate(client, state, args.dry_run)
```

- [ ] **Step 3: Test migration (dry run)**

```bash
source .venv/bin/activate
python scripts/sync-notion.py migrate --dry-run
```

Verify output lists all pages from planning_logs and adr_registry with `[dry-run]` prefix.

- [ ] **Step 4: Run migration for real**

```bash
python scripts/sync-notion.py migrate
```

Verify in Notion: all pages appear in Archive with correct Type tags and properties.

- [ ] **Step 5: Commit**

```bash
git add scripts/sync-notion.py data/notion-sync-state.json
git commit -m "feat(notion): add migrate command for database consolidation"
```

---

### Task 8: Wire sync-all into Claude Code skills

**Files:**
- Modify: `.claude/skills/handoff/SKILL.md:161-170`
- Modify: `.claude/skills/pickup/SKILL.md:20`
- Modify: `.claude/skills/ship-it/SKILL.md` (add step after push)
- Modify: `.claude/skills/codebase-audit/SKILL.md:229-246`
- Modify: `.claude/skills/discovery/SKILL.md` (add sync step)

- [ ] **Step 1: Update handoff SKILL.md**

Replace Phase 5.5 (lines 161-170):

```markdown
## Phase 5.5: Sync All Docs to Notion

Run the full Notion reconciliation (Archive, Sprints, API Reference):

\`\`\`bash
source .venv/bin/activate && python scripts/sync-notion.py sync-all --incremental 2>&1
\`\`\`

If the sync fails (missing NOTION_TOKEN, API errors), note the failure in SESSION_HANDOFF.md under Known Issues — do NOT block the rest of the handoff.
```

- [ ] **Step 2: Update pickup SKILL.md**

Line 20 already reads the whiteboard — add a sync step after the test baseline (after step 7):

Add as step 8 (renumber existing step 8 to 9):

```markdown
8. **Sync Notion** — run `source .venv/bin/activate && python scripts/sync-notion.py sync-all --incremental 2>&1` to push any docs changed between sessions. If it fails, note in pickup summary but don't block.
```

- [ ] **Step 3: Update ship-it SKILL.md**

Add after step 9 (Push) and before step 10 (Report):

```markdown
9.5. **Sync Notion:** `source .venv/bin/activate && python scripts/sync-notion.py sync-all --incremental 2>&1`
```

- [ ] **Step 4: Update codebase-audit SKILL.md**

Replace the Notion Sync Verification section (Phase 9.5, lines 233-246):

```markdown
### Notion Sync

Run the full reconciliation and verify it completes cleanly:

\`\`\`bash
source .venv/bin/activate && python scripts/sync-notion.py sync-all --incremental 2>&1
\`\`\`

Then check for drift:
- **Sync state freshness**: Check `data/notion-sync-state.json` — when was the last successful push?
- **Whiteboard check**: Run `python scripts/sync-notion.py read-whiteboard 2>&1` — surface any unacted notes.
```

- [ ] **Step 5: Update discovery SKILL.md**

Add a sync step at the end of the skill (after the discovery doc is written and committed):

```markdown
## Notion Sync

Push the new discovery to Notion:

\`\`\`bash
source .venv/bin/activate && python scripts/sync-notion.py sync-all --incremental 2>&1
\`\`\`
```

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/handoff/SKILL.md .claude/skills/pickup/SKILL.md .claude/skills/ship-it/SKILL.md .claude/skills/codebase-audit/SKILL.md .claude/skills/discovery/SKILL.md
git commit -m "feat(notion): wire sync-all into pickup, discovery, ship-it, handoff, codebase-audit skills"
```

---

### Task 9: Update documentation

**Files:**
- Modify: `docs/superpowers/specs/2026-03-24-notion-sync-design.md` (mark superseded)
- Modify: `CLAUDE.md` (update project structure reference)

- [ ] **Step 1: Mark old spec as superseded**

Add to the top of `docs/superpowers/specs/2026-03-24-notion-sync-design.md`:

```markdown
> **SUPERSEDED** by `docs/superpowers/specs/2026-03-25-notion-sync-v2-design.md` (2026-03-25)
```

- [ ] **Step 2: Update CLAUDE.md if needed**

If any project structure references changed (database names, script commands), update the relevant sections.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-03-24-notion-sync-design.md CLAUDE.md
git commit -m "docs: mark old Notion sync spec as superseded, update CLAUDE.md"
```

---

## Execution Order

Tasks 1-7 are sequential (each builds on the previous). Task 8 (skill wiring) can run in parallel with Task 7 (migrate). Task 9 (docs) runs last.

```
Task 1 (consolidate) → Task 2 (API ref) → Task 3 (whiteboard) → Task 4 (sync-sprints) → Task 5 (sync-all) → Task 6 (create-sprint-item) → Task 7 (migrate) ─┐
                                                                                                                                                                  ├→ Task 9 (docs)
                                                                                                                                          Task 8 (skill wiring) ─┘
```

## Total Scope

- ~9 tasks, ~35 steps
- Estimated: single focused session
- All changes in one file (`scripts/sync-notion.py`) plus 5 skill files and 2 doc files
- Manual Notion setup required before Task 1 (create API Reference DB, add Archive properties)
