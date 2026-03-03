# Sprint 12: Health Dashboard & Whoop Integration

**Created:** 2026-03-03
**Status:** PLANNED
**Priority:** P1 — Personal intelligence layer
**Estimated Effort:** ~17 days (~102 hours)
**Prerequisites:** Sprint 11 (Command Center layout, health sub-section placeholder)

---

## Objective

Build the health sub-dashboard in Command Center with Sleep/Nutrition/Fitness visualizations, integrate Whoop API for proprietary data (Strain, Recovery, 5-stage sleep), add labs & prescriptions (manual + Apple Health Records), and wire AI health analysis into the daily briefing.

### Health Data Compliance Requirements (Audit 2026-03-03)

> ⚠️ These compliance items are **prerequisites** — define BEFORE implementation begins.

1. **Data retention policy:** Define max retention period for clinical data (labs, prescriptions). Implement `DELETE /v1/health_data/purge-all` for user data deletion and `GET /v1/health_data/export` for data portability.
2. **PII scrubbing:** Lab PDFs contain SSN, DOB, addresses. Add PII detection pass before storing extracted text — strip everything except clinical values + test names.
3. **Audit trail:** AuditLogger events for all `/v1/health_data/*` and `/v1/whoop/*` endpoint access.
4. **AI disclaimer enforcement:** Post-processing filter scans LLM health output for diagnostic language ("you have", "diagnosis", "you should take"). Reject and regenerate if detected.
5. **HealthKit data isolation:** Raw HealthKit values must NOT be sent in cloud LLM prompts. Use `HealthDataSanitizer` to replace raw values with aggregated summaries.
6. **Whoop token tier:** Whoop OAuth tokens must be stored in `sensitive` credential tier (Fernet + Keychain), same as cloud provider API keys.
7. **FHIR placeholder:** Remove `fhir_client.py` placeholder to avoid confusion. Document FHIR as Phase 2.

## Deliverables

1. Health sub-dashboard in Command (Sleep, Fitness, Nutrition cards)
2. Whoop API module with OAuth2 integration
3. Clinical data module (labs, prescriptions) with PDF parsing
4. AI health analysis integrated into daily briefing
5. Trend visualizations (7/30/90-day sparklines)

---

## Task Breakdown

### 12.1 Health Sub-Dashboard Layout (~2 days)

**macOS components:**
- `macOS/Views/Command/HealthDashboardView.swift` — Container for health cards
- `macOS/Views/Command/SleepCard.swift` — Sleep stage breakdown + trend
- `macOS/Views/Command/FitnessCard.swift` — Strain, exercise, heart rate
- `macOS/Views/Command/NutritionCard.swift` — Placeholder + manual logging (future)

**Layout:**
```
┌──────────────────────────────────────────────────────────────┐
│  Health Dashboard                                [sticky hdr] │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │    SLEEP      │  │   FITNESS    │  │   NUTRITION      │   │
│  │              │  │              │  │                  │   │
│  │  ████████░░  │  │  Strain: 14  │  │   [Coming Soon]  │   │
│  │  7.2h / 8h   │  │  ▃▅▇▅▃▂▁    │  │                  │   │
│  │              │  │  Exercise:   │  │   Log Food  [+]  │   │
│  │  Deep: 1.5h  │  │  45 min      │  │                  │   │
│  │  REM: 2.1h   │  │  Avg HR: 72  │  │                  │   │
│  │  Light: 3.6h │  │  Peak HR:165 │  │                  │   │
│  │  ▃▅▇▅▃▇▅    │  │              │  │                  │   │
│  │  7-day trend  │  │  7-day trend │  │                  │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  📋 Analysis Card                                         │ │
│  │                                                            │ │
│  │  Recent Labs ─────────────────────────────────            │ │
│  │  Last drawn: Feb 15, 2026                                 │ │
│  │  • Vitamin D: 32 ng/mL (normal) • TSH: 2.1 (normal)     │ │
│  │  [View All Labs →]                                        │ │
│  │                                                            │ │
│  │  Active Prescriptions ────────────────────────            │ │
│  │  • Lisinopril 10mg daily  • Vitamin D3 5000IU daily      │ │
│  │  [View All →]                                             │ │
│  │                                                            │ │
│  │  🤖 Copilot Insights ─────────────────────────            │ │
│  │  "Your deep sleep improved 12% this week, likely          │ │
│  │  correlating with reduced screen time after 9pm..."       │ │
│  └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

**Data sources for cards:**
- Sleep: `GET /v1/health_data/summary` (HealthKit) + `GET /v1/whoop/sleep` (Whoop 5-stage)
- Fitness: `GET /v1/health_data/trend/exercise_minutes` + `GET /v1/whoop/strain`
- Nutrition: Placeholder (manual logging deferred to future sprint)

**Trend sparklines:** Mini bar charts (7-day) rendered with SwiftUI `Path` or `Chart` framework (iOS 16+ / macOS 13+).

### 12.2 Whoop API Integration (~4 days)

**Research finding confirmed:** Whoop does NOT sync to Apple Health:
- ❌ Strain scores (proprietary algorithm)
- ❌ Recovery scores (proprietary algorithm)
- ❌ 5-stage sleep breakdown (only awake/asleep to HealthKit)
- ❌ HRV in RMSSD format (Apple uses SDNN)
- ❌ Sleep disturbances count
- ❌ Activity zones

**Verdict:** Direct API integration justified — these are Whoop's core value metrics.

**New module:**
```
hestia/whoop/
├── __init__.py           # get_whoop_manager() factory
├── models.py             # WhoopRecovery, WhoopStrain, WhoopSleep, WhoopWorkout
├── client.py             # Whoop API client (REST + OAuth2)
├── manager.py            # WhoopManager (sync, cache, aggregate)
├── database.py           # SQLite storage
└── oauth.py              # Whoop OAuth2 helper
```

**Whoop API v1 endpoints consumed:**
| Endpoint | Data | Use |
|----------|------|-----|
| `GET /v1/cycle` | Daily physiological cycles | Strain score, day strain |
| `GET /v1/recovery` | Recovery score, HRV (RMSSD), resting HR, SpO2 | Recovery card, metrics |
| `GET /v1/sleep` | 5-stage breakdown (awake, light, REM, deep), disturbances, efficiency | Sleep card |
| `GET /v1/workout` | Individual workouts, strain, HR zones, duration | Fitness card |

**Whoop OAuth2 flow:**
1. Register app at [developer.whoop.com](https://developer.whoop.com)
2. `POST /v1/whoop/authorize` → generates auth URL with scopes: `read:recovery read:cycles read:sleep read:workout read:profile`
3. User authorizes in browser → redirect to callback
4. `POST /v1/whoop/callback` → exchange code for tokens → store refresh token in Keychain **(`sensitive` credential tier — Fernet + Keychain AES-256)**
5. Auto-refresh access tokens using shared `OAuthManager` base class (extracted in Sprint 9)

**Hestia API endpoints:**
```
POST   /v1/whoop/authorize        → { auth_url: str }
POST   /v1/whoop/callback         → { connected: bool, user_name: str }
POST   /v1/whoop/sync             → { synced: bool, records: int, last_sync: datetime }
GET    /v1/whoop/recovery          → { score: float, hrv_rmssd: float, resting_hr: int, spo2: float }
GET    /v1/whoop/strain            → { day_strain: float, workouts: List[WhoopWorkout] }
GET    /v1/whoop/sleep             → { total_hours: float, stages: SleepStages, efficiency: float, disturbances: int }
GET    /v1/whoop/status            → { connected: bool, last_sync: datetime, token_valid: bool }
DELETE /v1/whoop/disconnect        → { disconnected: bool }
```

**Sync strategy:** Pull last 7 days on connect, then daily sync via Order (or background task). Cache in SQLite with 1-hour TTL for display.

**macOS components:**
- `macOS/Views/Settings/WhoopAuthSheet.swift` — OAuth2 connection flow (in Resources section)
- `macOS/Services/APIClient+Whoop.swift` — endpoint wrappers

### 12.3 Clinical Data Module (~5 days)

**New module:**
```
hestia/health/clinical/
├── __init__.py           # get_clinical_manager() factory
├── models.py             # LabResult, LabPanel, Prescription, ClinicalRecord
├── manager.py            # ClinicalManager
├── database.py           # SQLite for labs/prescriptions
├── pdf_parser.py         # Extract lab values from PDF uploads
└── fhir_client.py        # Apple Health Records (future)
```

**Data models:**
```python
class LabResult(BaseModel):
    id: str
    test_name: str          # "Vitamin D, 25-Hydroxy"
    value: float
    unit: str               # "ng/mL"
    reference_low: Optional[float]
    reference_high: Optional[float]
    status: Literal["normal", "low", "high", "critical"]
    drawn_date: date
    source: Literal["manual", "pdf_upload", "health_records"]
    panel_name: Optional[str]  # "Comprehensive Metabolic Panel"

class Prescription(BaseModel):
    id: str
    medication_name: str    # "Lisinopril"
    dosage: str             # "10mg"
    frequency: str          # "daily"
    prescriber: Optional[str]
    start_date: date
    end_date: Optional[date]
    is_active: bool
    notes: Optional[str]
    source: Literal["manual", "health_records"]
```

**API endpoints:**
```
POST   /v1/health_data/labs              → Upload lab PDF or manual entry
GET    /v1/health_data/labs              → List lab results (filter by panel, date range)
GET    /v1/health_data/labs/{lab_id}     → Get specific lab detail
DELETE /v1/health_data/labs/{lab_id}     → Delete lab result

POST   /v1/health_data/prescriptions     → Add prescription (manual entry)
GET    /v1/health_data/prescriptions     → List active prescriptions
PUT    /v1/health_data/prescriptions/{id} → Update prescription
DELETE /v1/health_data/prescriptions/{id} → Discontinue prescription
```

**PDF lab parser (`pdf_parser.py`):**
- Uses `pdfplumber` or `pymupdf` to extract text from uploaded PDF
- Regex patterns for common lab formats (Quest, LabCorp, hospital systems)
- LLM fallback: If regex fails, send extracted text to Qwen 7B with structured extraction prompt
- Output: List[LabResult] with confidence scores
- Low-confidence results flagged for manual review

**macOS components:**
- `macOS/Views/Command/LabsDetailView.swift` — Full lab history with trends
- `macOS/Views/Command/PrescriptionsView.swift` — Active prescriptions list
- `macOS/Views/Command/LabUploadSheet.swift` — PDF upload + manual entry form
- `macOS/Views/Command/PrescriptionFormSheet.swift` — Add/edit prescription
- `macOS/Services/APIClient+Clinical.swift` — endpoint wrappers

### 12.4 AI Health Analysis in Daily Briefing (~1 day)

**Extend `BriefingGenerator`:**

New `BriefingSection` type: `HEALTH_ANALYSIS`

**Generation pipeline:**
1. Fetch latest health summary (HealthKit + Whoop if connected)
2. Fetch recent lab results (last 90 days)
3. Fetch active prescriptions
4. Construct analysis prompt:

```
Based on the following health data for the user, provide 2-3 brief insights:

Recent Health Metrics:
- Sleep: {sleep_data}
- Recovery: {recovery_score} ({whoop_or_hrv})
- Exercise: {exercise_summary}
- Resting HR trend: {trend}

Recent Labs (within 90 days):
{lab_results}

Active Prescriptions:
{prescriptions}

Provide:
1. One trend observation (positive or concerning)
2. One correlation insight (connecting two data points)
3. One actionable recommendation

IMPORTANT: Include "This is not medical advice" disclaimer.
```

5. **HealthDataSanitizer (audit addition):** Before sending to cloud LLM, replace raw HealthKit/Whoop values with aggregated summaries. Never send raw daily values — use weekly averages, trends, and ranges.
6. LLM generates analysis (cloud provider preferred for quality)
7. **Post-processing filter (audit addition):** Scan LLM output for diagnostic language patterns. If detected ("you have", "diagnosis", "you should take", "condition"), reject and regenerate with stronger disclaimer emphasis.
8. Include in briefing response as HEALTH_ANALYSIS section

**No new endpoint needed** — rides on existing `GET /v1/proactive/briefing`.

### 12.5 PDF Lab Parser Detail (~2 days)

**Common lab PDF formats to handle:**

```python
# Quest Diagnostics pattern
QUEST_PATTERN = re.compile(
    r'(?P<test_name>[A-Za-z\s,\-]+)\s+'
    r'(?P<value>[\d.]+)\s+'
    r'(?P<unit>[a-zA-Z/%]+)\s+'
    r'(?P<ref_range>[\d.]+-[\d.]+)'
)

# LabCorp pattern (slightly different layout)
LABCORP_PATTERN = re.compile(...)

# Generic "Name: Value Unit (Ref: Low-High)" pattern
GENERIC_PATTERN = re.compile(...)
```

**Pipeline:**
1. Extract text from PDF → split into lines
2. **PII scrubbing pass (audit addition):** Strip SSN (`\d{3}-\d{2}-\d{4}`), DOB, addresses, phone numbers. Store ONLY test names, values, units, reference ranges.
3. Detect lab provider (Quest, LabCorp, etc.) from header/footer
4. Apply provider-specific regex
5. For unmatched lines → batch send to LLM for extraction (**send only scrubbed text, never raw PII**)
6. Return results with confidence: regex match = 0.95, LLM extract = 0.7
7. Flag results with confidence < 0.8 for manual review

---

## Testing Plan

| Area | Test Count | Type |
|------|-----------|------|
| Health dashboard rendering | 4 | UI |
| Whoop OAuth2 flow | 4 | Integration |
| Whoop data sync + cache | 5 | API |
| Whoop recovery/strain/sleep endpoints | 4 | API |
| Clinical manager CRUD | 6 | Unit |
| Lab PDF parser (Quest, LabCorp, generic) | 6 | Unit |
| Lab PDF parser — negatives (malformed, empty, non-lab, multi-page) | 4 | Unit |
| Lab PDF parser — PII scrubbing (SSN, DOB, address stripped) | 3 | Security |
| Lab PDF parser LLM fallback | 3 | Integration |
| Prescription CRUD endpoints | 5 | API |
| Prescription validation (end_date before start_date) | 1 | Unit |
| Health analysis in briefing | 4 | Integration |
| Health analysis disclaimer enforcement (diagnostic language blocked) | 2 | Integration |
| HealthDataSanitizer — raw values not in LLM prompts | 2 | Security |
| Health data audit trail (all endpoint access logged) | 2 | Security |
| Whoop API rate limiting + backoff | 2 | Integration |
| Sleep/Fitness card data binding | 3 | UI |
| Trend sparkline rendering | 2 | UI |
| Clinical API endpoints | 5 | API |
| **Total** | **~51** | |

## SWOT

| | Positive | Negative |
|---|---|---|
| **Strengths** | HealthKit integration already complete (28 metrics). Whoop API well-documented REST. LLM analysis runs on existing cloud providers. Briefing generator has section architecture. | Largest sprint (17 days). Two external auth flows (Whoop + Gmail from Sprint 9). PDF parsing is inherently messy. Clinical data has regulatory sensitivity. |
| **Opportunities** | Health copilot with labs + prescriptions + wearable data is genuinely novel. Whoop Strain/Recovery is unique value. AI health insights in daily briefing is powerful. | Whoop API may have rate limits or require developer approval. Lab interpretation by AI carries liability. Apple Health Records requires participating provider. |

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Whoop developer access delays | Apply early. Fallback: HealthKit-only health dashboard ships without Whoop. Whoop added when approved. |
| PDF lab format variability | Regex + LLM dual-path. Flag low-confidence results. Allow manual correction. |
| Clinical data liability | Strong disclaimers on ALL AI analysis. "Not medical advice" banner on health card. No diagnostic claims. |
| Whoop API changes | Abstract behind `BaseWearableProvider` interface. Same pattern as email providers. |

## Definition of Done

- [ ] Health sub-dashboard visible in Command (scroll down)
- [ ] Sleep card shows HealthKit data + Whoop 5-stage breakdown (if connected)
- [ ] Fitness card shows exercise minutes, heart rate, Whoop strain (if connected)
- [ ] Nutrition card shows "Coming Soon" with manual log placeholder
- [ ] Whoop connected via OAuth2 flow in Resources settings
- [ ] Whoop data syncing daily with 1-hour cache TTL
- [ ] Labs uploadable via PDF or manual entry
- [ ] Lab PDF parser extracts results from Quest/LabCorp formats
- [ ] Prescriptions manageable (add, edit, discontinue)
- [ ] Analysis card in Command shows labs summary + prescription list + AI insights
- [ ] AI health analysis included in daily briefing
- [ ] "Not medical advice" disclaimer on all health AI output — **enforced by post-processing filter**
- [ ] PII scrubbing strips SSN, DOB, addresses from lab PDFs before storage
- [ ] HealthDataSanitizer prevents raw values in cloud LLM prompts
- [ ] AuditLogger events for all health data endpoint access
- [ ] Whoop tokens in `sensitive` credential tier (Fernet + Keychain)
- [ ] Data retention policy defined and deletion endpoint implemented
- [ ] `fhir_client.py` placeholder removed (FHIR documented as Phase 2)
- [ ] **Decision Gate 3:** Health integration worth compliance burden? Whoop approved? → Go/No-Go on Active Inference
- [ ] All tests passing (existing + ~65 new)
