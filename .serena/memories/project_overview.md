# Hestia Project Overview

Hestia is a locally-hosted personal AI assistant on Mac Mini M1. Jarvis-like: competent, adaptive, sardonic, anticipates needs.

## Three Modes
- `@Tia` (Hestia — daily ops)
- `@Mira` (Artemis — Socratic teaching)
- `@Olly` (Apollo — focused dev)

## Tech Stack
- Hardware: Mac Mini M1 (16GB)
- Model: Qwen 2.5 7B (Ollama, local) + cloud providers (Anthropic/OpenAI/Google)
- Backend: Python 3.9+, FastAPI, 116 endpoints across 20 route modules
- Storage: ChromaDB (vectors) + SQLite (structured) + macOS Keychain (credentials)
- App: Native Swift/SwiftUI (iOS 26.0+ and macOS 15.0+)
- API: REST on port 8443 with JWT auth, HTTPS with self-signed cert
- Dev Tools: Claude Code (API billing) + Xcode
- CI/CD: GitHub Actions → Mac Mini (auto-deploy on push to main)

## Current Status
- MVP v1.0 complete, Intelligence v1.5 complete
- 1100 tests (1097 passing, 3 skipped), 25 test files
- All UI phases and sprint wiring complete
