# Session Handoff — 2026-03-23

## Mission
Fix the broken Research tab (empty Principles, disconnected Graph nodes) and broken Trading module ($250 paper mode, bots not executing trades). Then redesign the knowledge graph visualization.

## Completed

### Research Tab Fixes
- **Principles stale cache fallback** — `getStale()` fallback when server unreachable, error state UI with Retry button (`5495622`)
- **Distillation prompt sizing** — Reduced to 5 chunks x 150 chars (~428 tokens) to stay on PRIMARY model tier, avoiding model swap timeouts on Mac Mini (`db94061`)
- **Knowledge graph redesign** — Principles + Facts as nodes, hybrid edges (TOPIC_LINK + SHARED_ENTITY), degree centrality sizing, billboard text labels, topics/entities detail panel, default mode switched to facts (`854bbc5`)

### Trading Module Fixes
- **USDC-USD stablecoin crash** — `_get_portfolio_value()` crashed on `get_ticker("USDC-USD")`, returning 0 and silently skipping ALL bot trading cycles. Fixed in bot_runner, portfolio endpoint, positions endpoint, and manager (`fc2e424`, `a34fa01`, `c0f5975`)
- **Live mode switch** — Changed `trading.yaml` from `mode: "paper"` to `mode: "live"` (`a2d03f5`)
- **Bot service restart** — Restarted via launchd on Mac Mini, all 4 bots evaluating signals (currently HOLD — RSI in neutral zones)

### Releases
- **v1.1.8** (build 12) — Principles cache fix
- **v1.1.9** (build 13) — Full graph redesign + trading fixes

## In Progress
- **Fact extraction pipeline** — The 3-phase LLM extraction (`fact_extractor.py`) fails silently on Mac Mini. Same root cause as distillation: long prompts get routed to COMPLEX tier (deepseek-r1:14b), triggering model swaps that timeout. Needs the same fix applied to distillation (reduce prompt size or force PRIMARY tier). **File:** `hestia/research/fact_extractor.py`, methods `_phase1_entities()`, `_phase2_significance()`, `_phase3_prism()`. **Current state:** 0 facts, 0 entities, 0 communities on Mac Mini. 4 pending principles exist.
- **Community detection** — Depends on facts/entities existing first. API endpoint works (`POST /v1/research/communities/detect`), but needs data.

## Decisions Made
- **Hybrid edge model** — Principle-to-Principle via shared topics, Principle-to-Fact via shared entities, Fact-to-Fact via shared entities (not topics — Facts lack topic tags in the data model). Documented in `docs/plans/research-graph-redesign-second-opinion-2026-03-23.md`
- **Degree centrality for node sizing** — 70% connections + 30% original weight. Gemini + critic both agreed.
- **Keep 3D SceneKit, add labels** — Both reviewers suggested 2D pivot, but 3D is built. Billboard labels mitigate readability gap.
- **Trading live mode** — Paper soak complete, switched to live Coinbase trading with $270.75 actual balance.

## Test Status
- 2644+ backend tests passing (100%)
- macOS build clean (HestiaWorkspace scheme)
- CLI tests have import path issue (pre-existing, not from this session)

## Uncommitted Changes
None — all committed and pushed. Untracked files pre-date this session:
- `HestiaApp/iOS/steward-icon-knot-v3-teal-dark.png`
- `docs/mockups/`
- `docs/plans/consumer-product-strategy.md`

## Known Issues / Landmines
- **Mac Mini fact extraction is broken** — `POST /v1/research/facts/extract` returns `facts_created: 0` because the 3-phase LLM pipeline routes to COMPLEX tier and times out. The graph will be sparse (only 4 principles, no facts) until this is fixed.
- **Bot service uses launchd** — After code deploys, the bot service needs manual restart: `launchctl unload ~/Library/LaunchAgents/com.hestia.trading-bots.plist && pkill -9 -f bot_service && launchctl load ~/Library/LaunchAgents/com.hestia.trading-bots.plist`
- **Multiple stale Python processes on Mac Mini** — Previous debug sessions left orphaned Python processes. Check with `ps aux | grep python | grep -v grep` and kill stale ones.
- **App update delivery** — v1.1.9 is pushed but GitHub Actions needs to complete build/sign/notarize before Sparkle delivers it. User runs `/Applications/Hestia.app` (installed), NOT the Xcode build.
- **Trading bots all HOLD** — RSI values are in neutral zones for all 4 pairs. This is correct behavior — trades will execute when RSI hits oversold/overbought thresholds. No action needed.

## Process Learnings
- **Config in git = deploy overwrites**: `sed` changes to `trading.yaml` on Mac Mini were overwritten by `git pull`. Config changes must be committed to git, not applied locally.
- **Local server causes confusion**: Starting the local dev server while the app points at Mac Mini creates auth mismatches (different JWT secrets). Always test against Mac Mini directly.
- **Stablecoin handling was missing everywhere**: The USDC-USD bug existed in 4 places (bot_runner, portfolio endpoint, positions endpoint, manager). Pattern: any code that iterates exchange balances and calls `get_ticker(f"{currency}-USD")` needs stablecoin guards.
- **First-pass success**: 6/8 tasks completed on first try. Rework caused by: (1) wrong MacColors tokens, (2) local-vs-mini server confusion.

## Next Session: Fix Fact Extraction Pipeline

### Exact steps:

1. **Read** `hestia/research/fact_extractor.py` — understand the 3-phase pipeline (`_phase1_entities`, `_phase2_significance`, `_phase3_prism`)

2. **Diagnose** — Each phase sends a long prompt that exceeds the 500-token `complex_token_threshold`, routing to deepseek-r1:14b (COMPLEX tier). Apply the same fix as distillation: reduce prompt size to stay under 500 tokens on PRIMARY tier (qwen3.5:9b, already loaded).

3. **Fix Phase 1** (`_phase1_entities`): Truncate input text to ~150 chars. Target: <500 tokens total prompt.

4. **Fix Phase 2** (`_phase2_significance`): Reduce text excerpt and limit entity count.

5. **Fix Phase 3** (`_phase3_prism`): Reduce text excerpt, limit entity list, keep output format compact.

6. **Test locally**: `python -m pytest tests/test_research.py -v --timeout=30`

7. **Deploy to Mac Mini**: `git push` + restart server

8. **Trigger extraction**: `curl -X POST https://hestia-3.local:8443/v1/research/facts/extract -H "X-Hestia-Device-Token: $TOKEN" -d '{"time_range_days": 30}'`

9. **Trigger community detection**: `curl -X POST https://hestia-3.local:8443/v1/research/communities/detect -H "X-Hestia-Device-Token: $TOKEN"`

10. **Verify graph**: Open Research tab — should now show principles + facts + entities with edges and community clustering
