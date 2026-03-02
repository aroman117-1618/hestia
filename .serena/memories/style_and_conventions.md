# Style and Conventions

## Python
- Type hints: Always, every function signature
- Async/await: For all I/O
- Logging: `logger = get_logger()` — no arguments. Import from `hestia.logging`
- Config: YAML files, never hardcode
- Error handling: `sanitize_for_log(e)` in logs, generic messages in HTTP responses
- File naming: `snake_case.py`
- Manager pattern: `models.py` + `database.py` + `manager.py` per module
- Python 3.12 (not 3.13+)

## Swift/iOS
- `@MainActor ObservableObject` with `@Published`
- DesignSystem tokens
- No force-unwraps, `[weak self]` in closures
- `#if DEBUG` for all `print()`
- File naming: `UpperCamelCase.swift`

## Testing
- Always run full test suite after changes
- Use `--timeout=30` per-test
- pytest may hang on ChromaDB threads — handled by conftest.py exit hook
