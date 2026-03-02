# Task Completion Checklist

1. Run full test suite: `python -m pytest tests/ -v --timeout=30`
2. Ensure all tests pass before considering task complete
3. Kill stale server processes: `lsof -i :8443 | grep LISTEN` then `kill -9`
4. Update affected docs (CLAUDE.md, api-contract.md, decision-log.md)
5. For Swift changes: build BOTH targets (HestiaWorkspace + HestiaApp)
