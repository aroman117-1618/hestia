# Hestia Sentinel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy a layered supply chain defense system protecting hestia's Mac Mini production environment from dependency tampering, credential exfiltration, and runtime compromise.

**Architecture:** Four layers deployed sequentially: Layer 0 (hardened execution environment — dedicated user, egress firewall, credential migration), Layer 1 (CI/CD prevention — hash-locked deps, blocking pip-audit, .pth scanning), Layer 2 (runtime sentinel daemon — file integrity, credential access, DNS monitoring), Layer 3 (alerting and UI integration — push notifications, daily digest, System Status cards). The sentinel uses Atlas-compatible event schema and runs from system Python, isolated from the hestia venv.

**Tech Stack:** Python stdlib (sentinel), bash (scripts/deploy), macOS launchd, LuLu/pf (egress), SQLite (event store), SwiftUI (System Status cards)

**Spec:** `docs/superpowers/specs/2026-03-27-hestia-sentinel-design.md`
**Second Opinion:** `docs/plans/hestia-sentinel-second-opinion-2026-03-27.md`

**Tasks:** 20 tasks across 4 layers. Estimated 8-12 hours total.

---

*Plan document exceeds practical inline length. See the committed file for the full 20-task implementation plan with complete code for every step.*
