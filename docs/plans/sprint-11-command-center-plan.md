# Sprint 11: Command Center Redesign + MetaMonitor

**Created:** 2026-03-03
**Status:** PLANNED
**Priority:** P1 — Intelligence dashboard
**Estimated Effort:** ~15 days (~90 hours)
**Prerequisites:** Sprint 10 (OutcomeTracker, background sessions in Orders)
**Learning Cycle Phase:** B — Metacognitive Dual-Cycle

---

## Objective

Redesign Command Center with compact layout: week calendar (top), notification highlights + orders (middle), contextual auto-switching metrics (top-right), and integrate the MetaMonitor for Learning Cycle Phase B. Orders redesigned with Recurring/Scheduled sections and multi-step creation wizard.

## Deliverables

1. Week calendar grid (7-day) at top
2. Compacted notification bubbles alongside Active Orders
3. Contextual metrics (auto-switch: Personal ↔ System)
4. Orders redesign: Recurring + Scheduled sections, status lifecycle
5. Multi-step order creation wizard (Prompt → Resources → Schedule)
6. Health dashboard as scrollable sub-section (detailed in Sprint 12)
7. MetaMonitor background manager for self-evaluation
8. ConfidenceCalibrator feeding real data to metrics
9. KnowledgeGapDetector feeding insights to daily briefing

---

## Task Breakdown

### 11.1 Command Layout Restructure (~2 days)

**File:** `macOS/Views/Command/MacCommandView.swift` (refactor)

**Layout spec (full scroll with sticky section headers):**
```
┌────────────────────────────────────────────────────────────────┐
│  Command                                              [sticky] │
│                                                                 │
│  ┌────────────────────────────────────┐  ┌──────────────────┐ │
│  │      WEEK CALENDAR (7-day grid)    │  │  CONTEXTUAL       │ │
│  │  Mon  Tue  Wed  Thu  Fri  Sat  Sun │  │  METRICS          │ │
│  │  ═══  ═══  ═══  ═══  ═══  ═══  ═══│  │                   │ │
│  │  9am: Sync         Team            │  │  😴 Sleep: 7.2h   │ │
│  │  10am:             Mtg             │  │  💪 Recovery: 85% │ │
│  │  11am: Focus       ·              │  │  ⏰ Busy: 62%     │ │
│  │  ...                               │  │                   │ │
│  └────────────────────────────────────┘  └──────────────────┘ │
│                                                                 │
│  ┌──────────────────┐  ┌───────────────────────────────────┐  │
│  │ HIGHLIGHTS        │  │  ORDERS                           │  │
│  │                   │  │                                    │  │
│  │ 📬 3 Unread       │  │  Recurring ─────────────────      │  │
│  │ 📅 2 Events       │  │  🔄 Daily Brief     ● active      │  │
│  │ ⏰ 1 Reminder     │  │  🔄 Git Sync        ● active      │  │
│  │ 🔔 0 Alerts       │  │                                    │  │
│  │                   │  │  Scheduled ──────────────────      │  │
│  │                   │  │  📋 Research task   ◐ working      │  │
│  │                   │  │  📋 Email summary   ✓ completed    │  │
│  └──────────────────┘  │                                    │  │
│                         │  [+ New Order]                     │  │
│                         └───────────────────────────────────┘  │
│                                                                 │
│  ═══════════════ Health Dashboard ═══════════════ [sticky hdr] │
│  [Sprint 12 content — placeholder here]                        │
└────────────────────────────────────────────────────────────────┘
```

### 11.2 Week Calendar (~2 days)

**New convenience endpoint:** `GET /v1/command/calendar-week`
```python
class CalendarEvent(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    calendar_name: str
    is_all_day: bool
    location: Optional[str]

class CalendarDayResponse(BaseModel):
    date: str  # YYYY-MM-DD
    day_name: str
    events: List[CalendarEvent]

class CalendarWeekResponse(BaseModel):
    week_start: str
    week_end: str
    days: List[CalendarDayResponse]
    total_events: int
```

**Implementation:** Uses existing Apple Calendar CLI tool. Backend aggregates 7 days of events.

**macOS component:** `macOS/Views/Command/WeekCalendarView.swift`
- 7-column grid with day headers (Mon–Sun)
- Hour rows (configurable: 8am–8pm default)
- Event blocks color-coded by calendar source
- Today column highlighted with orange border
- Tap event → popover with details (title, time, location)
- Swipe left/right or arrow buttons to navigate weeks

### 11.3 Contextual Auto-Switch Metrics (~2 days)

**New endpoint:** `GET /v1/command/metrics`
```python
class PersonalMetrics(BaseModel):
    sleep_hours: Optional[float]
    recovery_pct: Optional[float]     # From Whoop (Sprint 12) or HRV proxy
    busyness_pct: float               # Calendar density: booked_hours / available_hours

class SystemMetrics(BaseModel):
    error_count_24h: int              # Failed orders + tasks + API errors
    avg_latency_ms: float             # Average response time
    learning_count_7d: int            # Principles distilled this week
    prediction_accuracy: Optional[float]  # From ConfidenceCalibrator

class CommandMetricsResponse(BaseModel):
    mode: Literal["personal", "system"]
    personal: PersonalMetrics
    system: SystemMetrics
    reason: str                       # "default_personal", "high_errors", "high_latency"
```

**Auto-switch logic:**
```python
def determine_mode(system: SystemMetrics) -> tuple[str, str]:
    if system.error_count_24h > 0:
        return "system", "high_errors"
    if system.avg_latency_ms > 500:
        return "system", "high_latency"
    return "personal", "default_personal"
```

**macOS component:** `macOS/Views/Command/ContextualMetricsView.swift`
- Compact card with 3 metric rows
- Smooth crossfade animation when switching between personal/system
- Subtle mode indicator: "🧠 System" or "💤 Personal" label
- Tap card → expanded view with 7-day trend sparklines

### 11.4 Compact Notification Highlights (~1 day)

**Refactor existing:** Notification bubbles in Command view → compact single card

**Data sources:**
- Unread emails: `GET /v1/inbox/messages?unread_only=true` → count
- Today's events: `GET /v1/command/calendar-week` → today's count
- Due reminders: `GET /v1/explorer/resources?type=reminder` → overdue + due today
- Alerts: `GET /v1/proactive/notifications` → unread count

**macOS component:** `macOS/Views/Command/NotificationHighlightsCard.swift`
- Single compact card with 4 rows (emoji + label + count)
- Tap any row → navigates to relevant Explorer section
- Counts refresh on view appear + 60s polling

### 11.5 Orders Redesign (~2 days)

**Two sections:**
1. **Recurring** — Orders with frequency ≠ ONCE. Tagged with 🔄
2. **Scheduled** — One-time orders + background sessions

**Status indicators:**
| Status | Icon | Color | Meaning |
|--------|------|-------|---------|
| drafted | ○ | gray | Created but not activated |
| scheduled | ◎ | blue | Queued for execution |
| working | ◐ | orange (pulsing) | Hestia actively processing |
| completed | ✓ | green | Done, results available |
| active | ● | green | Recurring order is enabled |
| inactive | ○ | gray | Recurring order is paused |

**macOS components:**
- `macOS/Views/Command/OrdersView.swift` — refactored with two sections
- `macOS/Views/Command/OrderCard.swift` — redesigned with status indicators
- Past/upcoming logic: show completed orders in a collapsible "Past" section

### 11.6 Order Creation Wizard (~2 days)

**macOS component:** `macOS/Views/Command/OrderCreationWizard.swift` (sheet/modal)

**Step 1: Draft the Prompt**
```
┌─────────────────────────────────────────┐
│  New Order                      Step 1/3│
│                                          │
│  What should Hestia do?                  │
│  ┌────────────────────────────────────┐ │
│  │ $ Summarize my unread emails and   │ │
│  │   flag anything from investors...  │ │
│  └────────────────────────────────────┘ │
│  Uses MarkdownEditorView (CLI-style)    │
│                                          │
│  Name: [Email Summary ▁▁▁▁▁]            │
│                                          │
│  [Cancel]                    [Next →]   │
└─────────────────────────────────────────┘
```

**Step 2: Connect Resources**
```
┌─────────────────────────────────────────┐
│  New Order                      Step 2/3│
│                                          │
│  What does Hestia need access to?        │
│                                          │
│  ☑ Email (Apple Mail)                    │
│  ☑ Email (Gmail)                         │
│  ☐ Calendar                              │
│  ☐ Reminders                             │
│  ☐ Notes                                 │
│  ☐ Files                                 │
│  ☐ GitHub                                │
│  ☐ Web (Firecrawl)                       │
│                                          │
│  [← Back]                    [Next →]   │
└─────────────────────────────────────────┘
```

Resources list populated dynamically from `GET /v1/tools` + connected integrations.

**Step 3: Set Schedule**
```
┌─────────────────────────────────────────┐
│  New Order                      Step 3/3│
│                                          │
│  When should this run?                   │
│                                          │
│  ○ Once                                  │
│    Date: [Mar 5, 2026]                  │
│    Time: [09:00 AM]                     │
│                                          │
│  ● Recurring                             │
│    Frequency: [Daily ▾]                 │
│    Time: [07:00 AM]                     │
│    Days: [M] [T] [W] [T] [F] [S] [S]  │
│           ●   ●   ●   ●   ●   ○   ○   │
│                                          │
│  ○ Save as Draft (run manually)          │
│                                          │
│  [← Back]               [Create Order]  │
└─────────────────────────────────────────┘
```

**On "Create Order":** Constructs `OrderCreateRequest` and `POST /v1/orders`. Uses existing backend — wizard is purely frontend.

### 11.7 MetaMonitor (Learning Cycle Phase B) (~4 days)

**New module:** `hestia/learning/meta_monitor.py`

**Components:**

#### MetaMonitor (`meta_monitor.py`)

> ⚠️ **Audit finding:** Run MetaMonitor analysis on schedule (hourly, not real-time) to manage CPU cost on M1. Add CPU budget monitoring.

Background async manager that runs **hourly** (not real-time) to analyze interaction logs for:
- **Confusion loops:** >3 back-and-forth messages on same topic in one session
- **Declining acceptance:** OutcomeTracker showing increasing correction rate over 7 days
- **Latency spikes:** Response times trending upward in specific domains
- **Pattern drift:** User behavior changing vs. stored patterns (from PatternDetector)

```python
class MetaMonitor:
    async def analyze(self) -> MetaMonitorReport:
        confusion_loops = await self._detect_confusion_loops()
        acceptance_trend = await self._analyze_acceptance_trend()
        latency_trend = await self._analyze_latency_trend()
        pattern_drift = await self._detect_pattern_drift()

        return MetaMonitorReport(
            confusion_loops=confusion_loops,
            acceptance_declining=acceptance_trend.is_declining,
            latency_spikes=latency_trend.spikes,
            stale_patterns=pattern_drift.stale_count,
            recommendations=self._generate_recommendations(...)
        )
```

#### ConfidenceCalibrator (`confidence_calibrator.py`)
Tracks prediction accuracy per domain:
```python
class ConfidenceCalibrator:
    # Per-domain tracking
    domains: Dict[str, DomainConfidence]

    async def record_prediction(self, domain: str, predicted: Any, actual: Any):
        error = self._compute_error(predicted, actual)
        self.domains[domain].update(error)

    def get_calibration(self, domain: str) -> float:
        """Returns 0.0-1.0 calibration score. 1.0 = perfectly calibrated."""
        return self.domains[domain].accuracy
```

Feeds into CommandMetrics: `learning_count` = validated principles this week, `prediction_accuracy` = overall calibration score.

#### KnowledgeGapDetector (`knowledge_gap_detector.py`)
Identifies areas where Hestia has low confidence AND low data:
```python
class KnowledgeGapDetector:
    async def detect_gaps(self) -> List[KnowledgeGap]:
        """Find domains where we're uncertain and data-poor."""
        gaps = []
        for domain, confidence in self.calibrator.domains.items():
            data_points = await self._count_interactions(domain)
            if confidence.accuracy < 0.5 and data_points < 10:
                gaps.append(KnowledgeGap(
                    domain=domain,
                    confidence=confidence.accuracy,
                    data_points=data_points,
                    suggested_question=await self._generate_question(domain)
                ))
        return sorted(gaps, key=lambda g: g.confidence)
```

**Integration with daily briefing:** KnowledgeGapDetector output feeds into BriefingGenerator as a new section:
```
Areas where I'm learning:
- Your weekend project selection (30% accuracy, 4 data points)
  → "What drives your choice of weekend projects?"
- Email triage priorities (45% accuracy, 8 data points)
  → "Which emails do you consider most urgent?"
```

### 11.8 Self-Healing Foundation (~4 hours)

> **Added 2026-03-04** from Self-Healing Loop Assessment (`docs/discoveries/self-healing-loop-assessment-2026-03-04.md`).

#### 11.8a Read-Only Settings Tools (~1 hour)

**New file:** `hestia/execution/tools/settings_tools.py`

Register 3 diagnostic tools in `register_builtin_tools()`:

| Tool | Returns | Purpose |
|------|---------|---------|
| `get_user_settings` | UserSettings as JSON | Tia can introspect her config ("your timezone is set to Pacific") |
| `get_system_status` | Health check + active providers + model info | Tia can diagnose system issues |
| `get_user_timezone` | Current timezone string | Quick timezone lookup for tool responses |

Read-only — Tia can diagnose but not modify. Write tools deferred to Sprint 13 (requires safety framework).

#### 11.8b Outcome → Principle Batch Pipeline (~2 hours)

**New file:** `hestia/learning/outcome_pipeline.py`

Connects OutcomeTracker (Sprint 10) → PrincipleStore (Sprint 8):

1. Query OutcomeTracker: negative outcomes + quick_followup signals (last 24 hours)
2. Group by domain/topic using correction_type classification
3. **Hybrid threshold trigger**: distill when 3+ corrections in same domain within 24 hours, OR on daily schedule — whichever fires first
4. Feed grouped corrections into `PrincipleStore.distill_principles()`
5. All correction-derived principles start as `status=pending` — reviewed in `/research/principles` view

**Integration:** Scheduled via APScheduler alongside MetaMonitor (daily run). Threshold trigger runs on each new negative outcome.

#### 11.8c Correction Classification Enhancement (~1 hour)

**File:** `hestia/outcomes/manager.py` (enhance `detect_implicit_signal()`)

Add `correction_type` to OutcomeRecord metadata on follow-up detection:

| Type | Detection | Example |
|------|-----------|---------|
| `timezone` | Keywords: "EST", "PST", "timezone", "wrong time", "local time" | "That's 6 PM EST, not PST" |
| `factual` | Keywords: "actually", "no it's", "that's wrong", "incorrect" | "No, the meeting is Thursday" |
| `preference` | Keywords: "I prefer", "don't", "too", "less", "more" | "Too verbose, keep it short" |
| `tool_usage` | Keywords: "wrong tool", "use calendar", "check reminders" | "Check my calendar, not reminders" |

Simple keyword matching on user's follow-up message. Stored in `OutcomeRecord.metadata["correction_type"]`.

---

## Testing Plan

| Area | Test Count | Type |
|------|-----------|------|
| Calendar week endpoint | 4 | API |
| Contextual metrics calculation + auto-switch | 5 | Unit |
| Notification highlights aggregation | 3 | Integration |
| Orders Recurring/Scheduled sections | 4 | UI state |
| Order creation wizard (3-step flow) | 5 | UI + API |
| MetaMonitor confusion loop detection | 3 | Unit |
| MetaMonitor false positive rate (normal multi-turn should NOT trigger) | 3 | Unit |
| MetaMonitor acceptance trend analysis | 3 | Unit |
| MetaMonitor hourly scheduling + CPU budget | 2 | Integration |
| ConfidenceCalibrator accuracy tracking | 3 | Unit |
| ConfidenceCalibrator cold start (no data) | 2 | Unit |
| KnowledgeGapDetector gap identification | 2 | Unit |
| Order creation wizard validation (empty prompt, no resources) | 3 | UI |
| Read-only settings tools (get_user_settings, get_system_status, get_user_timezone) | 3 | Unit |
| Outcome → Principle pipeline (daily batch + threshold trigger) | 4 | Unit + Integration |
| Correction classification (keyword detection for 4 types) | 3 | Unit |
| Pipeline deduplication (same correction not distilled twice) | 2 | Unit |
| **Total** | **~54** | |

## SWOT

| | Positive | Negative |
|---|---|---|
| **Strengths** | Most data sources exist (calendar, health, orders). Order wizard is purely frontend. MetaMonitor provides genuine self-awareness. ConfidenceCalibrator makes "Learning" metric real. | Dense layout needs careful responsive design. Auto-switch thresholds require tuning. MetaMonitor adds background CPU cost. |
| **Opportunities** | Command becomes "at-a-glance brain" of Hestia. Order wizard lowers barrier to creating scheduled intelligence. Knowledge gaps in briefing surfaces genuinely useful questions. | Information density could overwhelm. Calendar data depends on TCC permissions. Constant strategy switching (from MetaMonitor) could feel erratic. |

## Definition of Done

- [ ] Week calendar renders real events from Apple Calendar
- [ ] Contextual metrics auto-switches between Personal and System
- [ ] Notification highlights show real unread/event/reminder/alert counts
- [ ] Orders split into Recurring (🔄) and Scheduled sections
- [ ] Order creation wizard: 3-step flow (Prompt → Resources → Schedule)
- [ ] Background sessions visible in Scheduled with `working` status
- [ ] MetaMonitor running hourly (not real-time), feeding metrics, with CPU budget monitoring
- [ ] ConfidenceCalibrator tracking per-domain accuracy
- [ ] KnowledgeGapDetector insights in daily briefing
- [ ] Full scroll with sticky section headers
- [ ] MetaMonitor false positive rate tested (normal conversations don't trigger confusion loops)
- [ ] ConfidenceCalibrator handles cold start gracefully (no data)
- [ ] Order wizard validates empty prompt, no resources selected
- [ ] Read-only settings tools registered and functional (get_user_settings, get_system_status, get_user_timezone)
- [ ] Outcome → Principle pipeline running (daily + 3-correction threshold trigger)
- [ ] Correction classification detecting timezone/factual/preference/tool_usage types
- [ ] Correction-derived principles appear in `/research/principles` view with pending status
- [ ] All tests passing (existing + ~54 new)
