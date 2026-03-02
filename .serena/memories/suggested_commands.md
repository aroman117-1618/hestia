# Suggested Commands

## Development
```bash
source .venv/bin/activate
python -m hestia.api.server            # Start server
python -m pytest tests/ -v --timeout=30 # Run tests
./scripts/test-api.sh                  # API smoke tests (14)
./scripts/deploy-to-mini.sh            # Deploy to Mac Mini
```

## Server Management
```bash
lsof -i :8443 | grep LISTEN            # Find server processes
kill -9 <PID>                           # Kill stale server
```

## Build (iOS + macOS)
```bash
xcodebuild -scheme HestiaWorkspace     # Build macOS
xcodebuild -scheme HestiaApp           # Build iOS
```

## Validation
```bash
hestia-preflight                       # On-demand validation
```
