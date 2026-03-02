# Hestia Development Plan

**Status**: All planned phases and workstreams COMPLETE as of March 2026.

---

### Sprint 6: Stability & Efficiency
| Title | Scope | Status |
|-------|-------|--------|
| Readiness Gate | ReadinessMiddleware returns 503 during startup | COMPLETE |
| Complete Shutdown | 15 managers closed in reverse order | COMPLETE |
| Uvicorn Recycling | limit_max_requests 5K + jitter 500 | COMPLETE |
| Parallel Init | 4-phase asyncio.gather for manager startup | COMPLETE |
| Lockfile | pip-compile requirements.in to pinned .txt | COMPLETE |
| Log Compression | Gzip >7d, delete >90d via launchd | COMPLETE |
| Cache-Control | Per-route caching headers | COMPLETE |

### Sprint 5: Audit + macOS Wiring
| Title | Scope | Status |
|-------|-------|--------|
| Proactive Auth Fix | Auth dependency standardization across 10 routes | COMPLETE |
| macOS Wiki | 4 views (sidebar, detail, article row, markdown) | COMPLETE |
| Explorer Resources | File browser + resources mode | COMPLETE |
| Resources Tab | LLMs, Integrations, MCPs tabs | COMPLETE |

### Sprint 4: Settings + Health
| Title | Scope | Status |
|-------|-------|--------|
| Dynamic Tool Discovery | Runtime tool inventory API | COMPLETE |
| Device Management UI | List, revoke, unrevoke devices | COMPLETE |
| macOS Health Redesign | ADR-036 health dashboard | COMPLETE |
| Proactive Settings | Briefing + notification preferences | COMPLETE |

### Sprint 3: Command Center
| Title | Scope | Status |
|-------|-------|--------|
| Newsfeed Backend | Materialized timeline + 5 API endpoints | COMPLETE |
| iOS Command Center | BriefingCard, FilterBar, NewsfeedTimeline | COMPLETE |
| macOS Command Center | Wiring to newsfeed API | COMPLETE |

### Sprint 2: Explorer
| Title | Scope | Status |
|-------|-------|--------|
| Explorer Backend | Resource aggregation + draft CRUD + TTL cache | COMPLETE |
| Explorer API | 6 endpoints for resources and drafts | COMPLETE |
| iOS Explorer Tab | File browser with resource cards | COMPLETE |

### Sprint 1: DevOps & Deployment
| Title | Scope | Status |
|-------|-------|--------|
| QR Invite Onboarding | 4 auth endpoints + iOS/macOS flows | COMPLETE |
| Permissions Harmony | iOS PermissionsOnboardingView (5 steps) | COMPLETE |
| CI/CD Pipeline | GitHub Actions deploy to Mac Mini | COMPLETE |

### macOS App
| Title | Scope | Status |
|-------|-------|--------|
| macOS Native App | 66 files, 6 views, icon sidebar, keyboard shortcuts | COMPLETE |
| Chat Panel | MacChatViewModel with per-message reactions | COMPLETE |
| App Polish | Volkhov fonts, responsive layout, app icon | COMPLETE |

### Wiki / Field Guide
| Title | Scope | Status |
|-------|-------|--------|
| Wiki Backend | AI generation, staleness detection, SQLite cache | COMPLETE |
| Wiki API | 5 endpoints (articles, generate, refresh) | COMPLETE |
| iOS Wiki Tab | Tabbed article browser with markdown rendering | COMPLETE |

### Apple HealthKit Integration
| Title | Scope | Status |
|-------|-------|--------|
| Health Backend | 28 metric types, daily sync, coaching | COMPLETE |
| Health API | 7 endpoints (sync, summary, trend, coaching) | COMPLETE |
| iOS HealthKit | HealthKitService + 5 chat tools | COMPLETE |

### iOS UI Phase 4: Integrations
| Title | Scope | Status |
|-------|-------|--------|
| Integrations View | Calendar, Reminders, Notes, Mail UI | COMPLETE |
| API Contract Rewrite | Full endpoint documentation refresh | COMPLETE |

### iOS UI Phase 3: Lottie + Neural Net
| Title | Scope | Status |
|-------|-------|--------|
| Lottie Animations | AI blob, typing indicator, motion fallback | COMPLETE |
| Settings Restructure | 6-section layout with Resources tab | COMPLETE |
| Neural Net Visualization | SceneKit 3D force-directed graph | COMPLETE |

### iOS UI Phase 2: Quick Wins
| Title | Scope | Status |
|-------|-------|--------|
| Memory Widget | Staged memory review in Command Center | COMPLETE |
| Byline Cleanup | Default Mode label removed | COMPLETE |

### iOS UI Phase 1: Bug Fixes
| Title | Scope | Status |
|-------|-------|--------|
| Face ID Auth | Biometric + device registration flow | COMPLETE |
| Notes CLI | Swift CLI for Apple Notes integration | COMPLETE |
| Tool Call JSON | Mixed text+JSON detection fix | COMPLETE |

### Intelligence WS4: Temporal Decay
| Title | Scope | Status |
|-------|-------|--------|
| Decay Algorithm | Per-chunk-type exponential decay | COMPLETE |
| Memory Config | Lambda values in memory.yaml | COMPLETE |

### Intelligence WS3: Council + SLM
| Title | Scope | Status |
|-------|-------|--------|
| 4-Role Council | Analyzer, Validator, Responder, Sentinel | COMPLETE |
| SLM Intent | qwen2.5:0.5b classification (~100ms) | COMPLETE |
| Dual-Path | Cloud parallel vs SLM-only fallback | COMPLETE |

### Intelligence WS2: Voice Journaling
| Title | Scope | Status |
|-------|-------|--------|
| SpeechAnalyzer | iOS speech recognition + transcript | COMPLETE |
| Quality Gate | LLM-powered word flagging + user review | COMPLETE |
| Journal Analysis | 3-stage intent extraction pipeline | COMPLETE |

### Intelligence WS1: Cloud LLM
| Title | Scope | Status |
|-------|-------|--------|
| 3-State Routing | disabled, enabled_smart, enabled_full | COMPLETE |
| Cloud Providers | Anthropic, OpenAI, Google integration | COMPLETE |
| Cloud API | 7 endpoints for provider management | COMPLETE |

### MVP Phase 7: API Layer
| Title | Scope | Status |
|-------|-------|--------|
| FastAPI REST | 72 initial endpoints | COMPLETE |
| JWT Auth | Device-based authentication | COMPLETE |
| HTTPS | Self-signed cert on port 8443 | COMPLETE |

### MVP Phase 6: Execution Layer
| Title | Scope | Status |
|-------|-------|--------|
| ToolExecutor | Dynamic tool dispatch | COMPLETE |
| Sandbox | File access controls | COMPLETE |
| Communication Gate | External approval workflow | COMPLETE |

### MVP Phase 5: Orchestration Layer
| Title | Scope | Status |
|-------|-------|--------|
| RequestHandler | Central request processing | COMPLETE |
| State Machine | Conversation state tracking | COMPLETE |
| Mode Manager | Tia/Mira/Olly mode switching | COMPLETE |

### MVP Phase 4: Memory Layer
| Title | Scope | Status |
|-------|-------|--------|
| ChromaDB | Vector storage for semantic search | COMPLETE |
| SQLite | Structured metadata storage | COMPLETE |
| Auto-Tagger | Automatic chunk categorization | COMPLETE |

### MVP Phase 3: Inference Layer
| Title | Scope | Status |
|-------|-------|--------|
| Ollama Integration | Local model inference | COMPLETE |
| Qwen 2.5 7B | Primary local model | COMPLETE |
| 3-Tier Routing | Model selection logic | COMPLETE |

### MVP Phase 2: Logging Layer
| Title | Scope | Status |
|-------|-------|--------|
| HestiaLogger | Structured logging with components | COMPLETE |
| AuditLogger | Security event auditing | COMPLETE |
| LogComponent Enum | 16 component categories | COMPLETE |

### MVP Phase 1: Security Layer
| Title | Scope | Status |
|-------|-------|--------|
| Keychain Integration | macOS Keychain for secret storage | COMPLETE |
| Fernet Encryption | Application-level encryption | COMPLETE |
| 3-Tier Credentials | Operational, sensitive, system partitioning | COMPLETE |

### MVP Phase 0: Project Setup
| Title | Scope | Status |
|-------|-------|--------|
| Python/FastAPI | Backend framework | COMPLETE |
| Mac Mini M1 | Hardware provisioning | COMPLETE |
| Project Structure | Module layout and conventions | COMPLETE |

---

## What's Next

No predefined phases remain. Future work is feature-driven:
- Field Guide UI restructure (thematic tabs, native diagrams, structured roadmap)
- Additional Apple integrations
- Performance optimization
- Multi-user support groundwork
