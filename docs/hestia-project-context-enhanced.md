# Hestia Project Context (Enhanced)

## Purpose of This Document

This file provides Claude with persistent context about the Hestia project. Add this to your Claude Project to ensure consistent, informed collaboration across conversations.

**Last Updated**: 2025-01-12 (iOS App Polish: Core Data, Orders, Calendar, Settings)

---

## Project Status Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Environment Setup | COMPLETE | Python 3.9, Ollama, Mac Mini 16GB |
| Security Foundation | COMPLETE | Keychain, Fernet, Secure Enclave |
| Logging | COMPLETE | JSON structured, audit trail |
| Inference | COMPLETE | Qwen 2.5 7B (local only) |
| Memory | COMPLETE | ChromaDB + SQLite, tag schema |
| Orchestration | COMPLETE | State machine, modes, validation, tool injection |
| Background Tasks | COMPLETE | Phase 4.5, SQLite queue, 7 endpoints, 60 tests |
| Execution | COMPLETE | Sandbox, gating, 23 tools |
| Apple Ecosystem | COMPLETE | Calendar, Reminders, Notes, Mail (20 tools) |
| REST API | COMPLETE | FastAPI, JWT auth, HTTPS/TLS, 25 endpoints |
| Native App | IN PROGRESS | SwiftUI app polished: Core Data, Orders, Calendar, Settings rebuilt |
| Security Hardening | COMPLETE | Phase 10: TLS, rate limiting, security headers |
| Proactive Intelligence | COMPLETE | Phase 9: briefings, patterns, interruption policy |

**Next Milestone**: Backend implementation for Orders/Agent Profiles/User Settings APIs

---

## Locked Decisions (Post Q&A Session - 2025-01-08)

### Security Posture
**Target**: Pentagon/CIA-level security
**Approach**: Defense-in-depth with hardware-backed security (Secure Enclave)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Credential Storage** | macOS Keychain + Secure Enclave, three partitions (operational/sensitive/system) | Hardware security, biometric gates, zero setup |
| **Encryption** | Double encryption (Fernet + Keychain AES-256) | Defense in depth |
| **Biometric Auth** | Face ID/Touch ID required for sensitive data | Seamless yet secure |
| **Audit Trail** | Complete logging (7-year retention for credential access) | Compliance best practices |
| **Data Retention** | Indefinite with annual review prompt | Long-term memory goal |
| **API Auth** | JWT device tokens | Simple, stateless, secure |

### Apple Ecosystem Integration (OAuth-Free)
**Strategy**: Leverage native integration, no OAuth needed for v1.0

| Component | Access Method | Capabilities |
|-----------|---------------|--------------|
| **Apple Mail** | SQLite query | Full read access to Gmail (synced via IMAP) |
| **Apple Calendar** | Swift CLI + EventKit | Full CRUD on all calendars |
| **Apple Reminders** | Swift CLI + EventKit | Full CRUD with all features |
| **Apple Notes** | Swift CLI + AppleScript | Text-only CRUD, attachments deferred |
| **Email Sending** | Deferred to v1.5 | Hestia drafts, user sends via Mail.app |

### Context Window Management (ADR-011)
**Challenge**: Mixtral 8x7B has 32K token limit

**Token Budget Allocation**:
- System prompt: 2K (fixed)
- Tool definitions: 1K (fixed)
- User model: 2K (summarized)
- Conversation history: up to 20K (sliding window)
- Memory retrieval: up to 4K (RAG-filtered)
- User input: ~3K (remaining)

---

## Project Summary

**Hestia** is a locally-hosted, single-agent AI system running on Andrew's Mac Mini. It serves as a personal operating layer providing:

- **Task delegation** with persistent context across sessions and devices
- **Research capabilities** including overnight autonomous research
- **Structured education** with competency tracking and Socratic teaching
- **Three operational modes**: Tia (default), Mira (learning), Olly (projects)

**Key mental model**: Hestia is like Jarvis from Iron Man—competent, adaptive, occasionally sardonic, anticipates needs without being emotionally solicitous.

---

## Identity Quick Reference

| Invoke | Name | Full Name | Focus |
|--------|------|-----------|-------|
| \`@Tia\` | Tia | Hestia | Default: daily ops, quick queries |
| \`@Mira\` | Mira | Artemis | Learning: Socratic teaching, research |
| \`@Olly\` | Olly | Apollo | Projects: focused dev, minimal tangents |

**Personality**: High sarcasm/wit, high adaptiveness/pragmatism, moderate empathy/curiosity, dry humor, never sycophantic.

---

## Technical Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| Hardware | Mac Mini M1, 16GB | Future: 64GB for Mixtral |
| Model | Qwen 2.5 7B | Via Ollama, local only |
| Language | Python 3.9+ | Backend implementation |
| API | FastAPI | REST on port 8443, JWT auth |
| App | Native Swift (SwiftUI) | iPhone, iPad, macOS |
| Vector DB | ChromaDB | Semantic search for memory |
| Structured DB | SQLite | Tags, metadata, relationships |
| Remote Access | Tailscale | Zero-config VPN |

### Development Tooling

| Tool | Purpose |
|------|---------|
| **Claude Code** | Primary development driver |
| **Xcode** | IDE for everything |

---

## Architecture Overview

```
Apple Devices (stateless terminals)
         |
    Tailscale + Biometric Auth
         |
    Access Layer (REST API, sessions, notifications)
         |
    Orchestration Layer (mode management, state machine, validation)
         |
    Memory Layer (user model, learning queue, research, staging)
         |
    Inference Layer (Qwen 2.5 7B via Ollama, local only)
         |
    Execution Layer (Apple ecosystem, tools, external gate)
         |
    Admin Layer (GUI dashboard, logs, health monitoring)
```

---

## REST API (Phase 6a - COMPLETE)

The API runs on port 8443 with JWT device authentication.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /v1/ping | No | Connectivity check |
| GET | /v1/health | No | System health status |
| POST | /v1/auth/register | No | Register device, get JWT |
| POST | /v1/chat | Yes | Send message to Hestia |
| GET | /v1/mode | Yes | Get current mode |
| POST | /v1/mode/switch | Yes | Switch persona mode |
| GET | /v1/memory/staged | Yes | List pending reviews |
| POST | /v1/memory/approve/{id} | Yes | Approve staged memory |
| GET | /v1/memory/search | Yes | Semantic search |
| POST | /v1/sessions | Yes | Create session |
| GET | /v1/sessions/{id}/history | Yes | Get conversation |
| GET | /v1/tools | Yes | List available tools |

**API Documentation**: http://localhost:8443/docs

---

## Design Principles

1. **Observability Over Determinism** - Log everything, enable replay
2. **Single Agent, Multiple Modes** - One model, three personas
3. **Governed Memory Persistence** - Staged for human review (ADR-002)
4. **Conservative Autonomy** - Default Level 2 (draft and confirm)
5. **Strict External Gate** - Nothing sent externally without approval
6. **Local-First, Local-Only** - All inference runs on local hardware. No cloud LLM dependencies.

---

## Current Phase

### MVP (v1.0)
- [x] Phase 0: Environment Setup
- [x] Phase 0.5: Security Foundation
- [x] Phase 1: Logging Infrastructure
- [x] Phase 2: Inference Layer
- [x] Phase 3: Memory Layer
- [x] Phase 4: Orchestration Layer
- [x] Phase 4.5: Background Task Management
- [x] Phase 5: Execution Layer
- [x] Phase 5.5: Apple Ecosystem
- [x] Phase 6a: REST API
- [ ] **Phase 6b: Native App Polish** <- CURRENT (scroll issue)
- [x] Phase 7: Integration & Hardening (TLS, Tailscale)
- [ ] Phase 8: Foundation Iteration (observational)

### Intelligence Enhancements (v1.5)
- [x] Phase 9: Proactive Intelligence (briefings, patterns, policy)
- [x] Phase 10: Security Hardening (TLS, rate limiting, headers)
- [ ] Phase 3.6: Confidence-Tracked Preferences
- [ ] Phase 8.5: Learning from History

---

## Native App (Phase 6b) - Current State

**HestiaApp** - SwiftUI app for iOS 16+

| Component | Status | Notes |
|-----------|--------|-------|
| Design System | COMPLETE | Colors, Typography, Spacing, Animations |
| Core Data | COMPLETE | Programmatic model (no .xcdatamodeld), entities for Orders, Executions, Agents |
| Models | COMPLETE | HestiaMode, Message, Order, AgentProfile, CalendarEvent, etc. |
| Services | COMPLETE | CalendarService (EventKit), OrdersService, APIClient, AuthService |
| Chat UI | COMPLETE | Bottom-anchored scroll, mode switching, typewriter effect |
| Command Center | COMPLETE | Orders/Alerts tabs, Calendar widget, Neural Net placeholder |
| Settings | COMPLETE | System Status, User Profile, Agent Profiles (3-slot), Server config |
| Memory Review | BUILT | Pending approval workflow |

**Completed This Session:**
1. Chat scroll fixed - bottom-anchored with proper keyboard avoidance
2. Calendar integration - EventKit with CalendarService protocol
3. CommandCenter - Modular widgets: Orders (CRUD), Alerts (execution history), Calendar
4. Settings - System health, profile editing, agent customization (3 slots)
5. Core Data - Full programmatic model with OrderEntity, OrderExecutionEntity, AgentProfileEntity
6. API Contract - Comprehensive endpoints for Orders, Agent Profiles, User Settings

**Known Issues:**
1. Mode invocation patterns updated to include "Hey Tia" etc. - needs iOS rebuild

---

## Test Coverage

| Component | Tests | Status |
|-----------|-------|--------|
| Inference | 11 | Passing |
| Memory | 33 | Passing |
| Orchestration | 61 | Passing |
| Execution | 47 | Passing |
| Apple | 30 | Passing |
| Tasks | 60 | Passing |
| **Total** | **242** | **All passing** |

---

## Reference Documents

- \`docs/hestia-initiative-enhanced.md\` - Complete specification
- \`docs/hestia-development-plan.md\` - Phase-by-phase build guide
- \`docs/hestia-decision-log.md\` - Architectural decisions
- \`docs/api-contract.md\` - REST API specification
- \`docs/ui-data-models.md\` - Frontend data structures
- \`docs/hestia-security-architecture.md\` - Security design

---

## Glossary

| Term | Meaning |
|------|---------|
| Tia | Default Hestia mode—general assistant |
| Mira | Artemis mode—learning and research |
| Olly | Apollo mode—focused project work |
| User model | Hestia's evolving understanding of the user |
| Staging layer | Proposed memory updates awaiting approval |
| External gate | Approval checkpoint for outbound communication |
| JWT | JSON Web Token for API authentication |

---

*Keep this document updated as the project evolves.*
