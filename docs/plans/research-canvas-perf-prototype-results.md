# Research Canvas — Performance Prototype Results

**Date:** 2026-03-24
**Tested on:** Mac Mini M1 16GB, Safari, via HTTP localhost
**Verdict:** GO — proceed with Phase 2

## Test Setup
- 300 nodes (default React Flow nodes), ~120 edges
- React Flow v12.6.0, single-file Vite bundle (499KB)
- Served via `python3 -m http.server` on Mac Mini, opened in Safari

## Results
- **Performance:** Acceptable at 300 nodes, described as "good but only just barely"
- **Rendering:** Nodes visible, pan/zoom functional, controls and minimap working
- **Route:** Hash routing (`#/research`) works correctly via HTTP (file:// URLs strip hash fragments in Safari)

## Key Design Insight (from Andrew)

**The 300-node stress test overestimates the real workload.** The Research Canvas is a focused workbench, not a dump of all entities:

- **Sidebar = inventory** — All memories, entities, principles, investigations live here (could be hundreds)
- **Canvas = workbench** — User selects specific items from the sidebar to build context for a principle (typically 20-50 nodes)
- **Distill flow** — User arranges selected items on canvas → "Distill Principle" → Hestia reviews and augments with her own understanding → presents in Principles UI for final review/edit/approve/reject

This means typical canvas load is **20-50 nodes** — well within the performance ceiling. The 300-node test provides comfortable headroom.

## Implications for Implementation
- No need for virtualization or lazy-loading optimizations in V1
- Node cap of 200 is unnecessary — sidebar filtering prevents canvas overload naturally
- Focus engineering effort on the sidebar search/filter UX (the "backpack") rather than canvas performance
- Distill Principle flow should send selected node IDs to Hestia, who enriches the principle with her broader knowledge (not just the visible canvas)
