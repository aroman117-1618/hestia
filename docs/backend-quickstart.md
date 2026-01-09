# Hestia Backend Quick Start Guide

**Status**: Phase 6a COMPLETE - REST API Ready
**Last Updated**: 2025-01-11

This guide explains how to run and test the Hestia backend.

---

## Quick Start

### Start the API Server

```bash
cd ~/hestia
source .venv/bin/activate
python -m hestia.api.server
```

The server runs on **port 8443** by default.

### Verify It's Running

```bash
# Ping check
curl http://localhost:8443/v1/ping

# Health check
curl http://localhost:8443/v1/health | jq
```

### Interactive API Docs

Open http://localhost:8443/docs for Swagger UI.

---

## Prerequisites

### On Mac Mini (Production Host)

```bash
# SSH to Mac Mini
ssh andrewroman117@hestia-3.local

# Check Ollama is running
curl http://localhost:11434/api/tags

# Verify models are available
/opt/homebrew/bin/ollama list
# Should show: qwen2.5:7b and/or mixtral:8x7b
```

### On Development Machine (MacBook)

```bash
cd ~/hestia

# Activate virtual environment
source .venv/bin/activate

# Verify Python version
python --version  # Should be 3.9+

# Install dependencies (if needed)
pip install -r requirements.txt
```

---

## API Endpoints

The REST API uses JWT device authentication. Register a device first, then use the token for authenticated requests.

### Public Endpoints (No Auth)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /v1/ping | Connectivity check |
| GET | /v1/health | System health status |
| POST | /v1/auth/register | Register device, get JWT token |

### Authenticated Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /v1/chat | Send message to Hestia |
| GET | /v1/mode | Get current mode |
| POST | /v1/mode/switch | Switch persona mode |
| GET | /v1/mode/{mode} | Get mode details |
| GET | /v1/memory/staged | List pending memory reviews |
| POST | /v1/memory/approve/{id} | Approve staged memory |
| POST | /v1/memory/reject/{id} | Reject staged memory |
| GET | /v1/memory/search | Semantic search |
| POST | /v1/sessions | Create session |
| GET | /v1/sessions/{id}/history | Get conversation history |
| DELETE | /v1/sessions/{id} | End session |
| GET | /v1/tools | List available tools |
| GET | /v1/tools/categories | List tool categories |
| GET | /v1/tools/{name} | Get tool details |

---

## Sample API Requests

### Register a Device

```bash
curl -X POST http://localhost:8443/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"device_name": "dev-mac", "device_type": "macos"}' | jq
```

Save the returned token for subsequent requests.

### Send a Message

```bash
TOKEN="your-jwt-token-here"

curl -X POST http://localhost:8443/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Hestia-Device-Token: $TOKEN" \
  -d '{
    "message": "Hello Tia!",
    "session_id": null
  }' | jq
```

### Switch Mode

```bash
curl -X POST http://localhost:8443/v1/mode/switch \
  -H "Content-Type: application/json" \
  -H "X-Hestia-Device-Token: $TOKEN" \
  -d '{"mode": "mira"}' | jq
```

### Search Memory

```bash
curl "http://localhost:8443/v1/memory/search?query=preferences&limit=5" \
  -H "X-Hestia-Device-Token: $TOKEN" | jq
```

### Get Pending Reviews

```bash
curl http://localhost:8443/v1/memory/staged \
  -H "X-Hestia-Device-Token: $TOKEN" | jq
```

---

## Running Tests

```bash
source .venv/bin/activate

# All tests (may take a while due to inference)
pytest tests/ -v

# Specific test file
pytest tests/test_orchestration.py -v

# Skip slow inference tests
pytest tests/ -v -k "not inference"

# With timeout (inference can be slow on first request)
pytest tests/ --timeout=600
```

---

## Testing Components Directly

For debugging, you can test backend components directly in Python.

### Test Inference Health

```python
import asyncio
from hestia.inference import get_inference_client

async def check_health():
    client = get_inference_client()
    health = await client.health_check()
    print(f"Status: {health['status']}")
    print(f"Local Ollama: {health['local']['ollama_available']}")
    print(f"Cloud API: {health['cloud']['status']}")
    await client.close()

asyncio.run(check_health())
```

### Test Memory Operations

```python
import asyncio
from hestia.memory import get_memory_manager

async def test_memory():
    manager = await get_memory_manager()

    # Store something
    chunk = await manager.store(
        content="User prefers detailed technical explanations",
        auto_tag=True
    )
    print(f"Stored chunk: {chunk.id}")

    # Search
    results = await manager.search(query="technical", limit=5)
    print(f"Found {len(results)} results")

asyncio.run(test_memory())
```

### Test Apple Integration (On Mac Mini)

```python
import asyncio
from hestia.apple.calendar import CalendarClient
from hestia.apple.reminders import RemindersClient

async def test_apple():
    cal = CalendarClient()
    calendars = await cal.list_calendars()
    print(f"Calendars: {len(calendars)}")

    events = await cal.get_today_events()
    print(f"Today's events: {len(events)}")

asyncio.run(test_apple())
```

**Note**: Requires Calendar/Reminders permissions on Mac Mini.

---

## Development vs Production

### Development Mode (Skip Auth)

```bash
HESTIA_DEV_MODE=true python -m hestia.api.server
```

### Production

```bash
python -m hestia.api.server
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HESTIA_DEV_MODE` | `false` | Skip auth in development |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `HESTIA_DATA_DIR` | `~/hestia/data` | Data storage directory |
| `HESTIA_LOG_DIR` | `~/hestia/logs` | Log directory |
| `HESTIA_API_PORT` | `8443` | API server port |

---

## Troubleshooting

### "Cannot connect to Ollama"

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# If not, start it
ollama serve &

# Or restart the service
brew services restart ollama
```

### "Model not found"

```bash
# Pull required model
ollama pull qwen2.5:7b
# Or for complex tasks
ollama pull mixtral:8x7b-instruct-v0.1-q4_K_M
```

### "Permission denied" for Apple APIs

On Mac Mini, grant permissions:
1. System Preferences > Privacy & Security > Calendars
2. System Preferences > Privacy & Security > Reminders
3. For Notes: May need AppleScript permissions
4. For Mail: Needs Full Disk Access

### Tests Timing Out

Mixtral on M1 can be slow on cold start (~30-60 seconds first request).

```bash
# Increase pytest timeout
pytest tests/ --timeout=600

# Or warm up the model first
curl http://localhost:11434/api/generate \
  -d '{"model": "qwen2.5:7b", "prompt": "Hello", "stream": false}'
```

---

## Project Structure

```
hestia/
├── hestia/
│   ├── api/              # REST API (Phase 6a - COMPLETE)
│   │   ├── server.py     # FastAPI app
│   │   ├── schemas.py    # Pydantic models
│   │   ├── middleware/   # Auth middleware
│   │   └── routes/       # API routes
│   ├── inference/        # Inference layer (COMPLETE)
│   ├── memory/           # Memory layer (COMPLETE)
│   ├── orchestration/    # Orchestration layer (COMPLETE)
│   ├── execution/        # Execution layer (COMPLETE)
│   └── apple/            # Apple ecosystem (COMPLETE)
├── HestiaApp/            # Native iOS/macOS app (Phase 6b - IN PROGRESS)
├── tests/                # Test suite (163 tests)
├── data/                 # SQLite, ChromaDB
├── logs/                 # Application logs
└── docs/                 # Documentation
```

---

## For iOS App Development

The native SwiftUI app (HestiaApp) includes:
- `MockHestiaClient` - Simulates backend responses for UI development
- `APIClient` - Real backend connection for production

During development, the app uses MockHestiaClient by default. To test against the real backend:

1. Start the API server (see above)
2. Update the app to use APIClient instead of MockHestiaClient
3. Ensure the device can reach the server (localhost for simulator, Tailscale for physical device)

---

## Quick Reference

```bash
# Start API server
source .venv/bin/activate && python -m hestia.api.server

# Run tests
python -m pytest tests/ -v

# API docs
open http://localhost:8443/docs

# Register device & get token
./scripts/test-api.sh
```
