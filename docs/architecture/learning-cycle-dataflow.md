# Learning Cycle Data Flow Architecture

**Created:** 2026-03-03 (from audit recommendation)
**Status:** Reference document — update as sprints complete

---

## Overview

The Neural Net Learning Cycle is threaded across Sprints 8–14. This document maps the full data flow from raw interaction signals to anticipatory behavior, ensuring all components are integrated correctly.

## Pipeline

```
Raw Signals
    │
    ├── Chat interactions ──────────┐
    ├── Tool usage logs ────────────┤
    ├── Calendar patterns ──────────┤
    ├── Health data ────────────────┤
    └── Outcome signals ────────────┤
                                    ▼
                    ┌───────────────────────────┐
                    │     PrincipleStore (S8)    │
                    │  ChromaDB: hestia_principles│
                    │  Distills: behavioral       │
                    │  principles from sessions   │
                    │  Human review in briefing   │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │   OutcomeTracker (S10)     │
                    │  SQLite: outcome_signals    │
                    │  Session-scoped correction  │
                    │  detection (not fixed 60s)  │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │    MetaMonitor (S11)       │
                    │  Hourly analysis (not RT)   │
                    │  Confusion loops, trends    │
                    │  Feeds: ConfidenceCalibrator │
                    │  Feeds: KnowledgeGapDetector │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │   WorldModel (S13)         │
                    │  3 layers (EMA updates):    │
                    │  Abstract → monthly         │
                    │  Routine  → weekly          │
                    │  Situational → per-interact  │
                    └─────────────┬─────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
    ┌─────────────┐   ┌──────────────────┐   ┌─────────────┐
    │ Prediction   │   │ Surprise          │   │ Curiosity   │
    │ Engine (S13) │   │ Detector (S13)    │   │ Drive (S13) │
    │              │   │ Quadratic error   │   │ Info-theory │
    │ Pre-interact │   │ Per-domain EMA    │   │ Observable  │
    │ predictions  │   │                   │   │ grounding   │
    └──────┬──────┘   └────────┬──────────┘   └──────┬──────┘
           │                   │                      │
           └───────────────────┼──────────────────────┘
                               ▼
                    ┌──────────────────────┐
                    │  RegimeSelector (S14) │
                    │  Configurable thresholds│
                    │  Hysteresis guard      │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ ANTICIPATORY  │  │ OBSERVANT    │  │ CURIOUS      │
    │ >0.8 conf     │  │ 0.4-0.8      │  │ <0.4 conf    │
    │ Auto-execute  │  │ Watch+learn  │  │ Ask questions │
    │ Draft orders  │  │ Log patterns │  │ Seek data     │
    └──────────────┘  └──────────────┘  └──────────────┘
```

## Data Stores

| Component | Store | Collection/Table | Sprint |
|-----------|-------|-----------------|--------|
| PrincipleStore | ChromaDB | `hestia_principles` | 8 |
| GraphBuilder | ChromaDB | `hestia_graph` (if needed) | 8 |
| OutcomeTracker | SQLite | `outcome_signals` | 10 |
| ConfidenceCalibrator | SQLite | `calibration_scores` | 11 |
| KnowledgeGapDetector | In-memory (from Calibrator) | — | 11 |
| WorldModel | SQLite | `world_model_state` | 13 |
| PredictionEngine | SQLite | `predictions` | 13 |
| SurpriseDetector | In-memory EMA + SQLite log | `surprise_log` | 13 |
| RegimeSelector | In-memory + config | `config/learning.yaml` | 14 |

## Key Dependencies

- PrincipleStore (S8) data consumed by WorldModel (S13) abstract layer
- OutcomeTracker (S10) signals consumed by MetaMonitor (S11) and PredictionEngine (S13)
- ConfidenceCalibrator (S11) scores consumed by RegimeSelector (S14)
- Health data (S12) feeds WorldModel (S13) situational layer (energy_proxy)

## Decision Gates

1. **After Sprint 8:** Is PrincipleStore producing useful principles? → Validate before building on it
2. **After Sprint 10:** Is OutcomeTracker collecting meaningful signals? → Required for MetaMonitor
3. **After Sprint 12:** Go/No-Go on full Active Inference vs. simplified heuristics

## Key Audit Decisions

- **EMA over Bayesian:** 7B model can't produce calibrated probability distributions
- **Quadratic surprise over free energy:** Dropped complexity_penalty (undefined, unnecessary)
- **Observable grounding:** CuriosityDrive questions must reference concrete data, not model state
- **Configurable thresholds:** Regime boundaries tunable via YAML, not hardcoded
- **Hysteresis:** Prevents rapid regime flapping when near threshold boundaries
