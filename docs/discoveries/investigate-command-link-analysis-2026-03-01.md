# Discovery Report: "Investigate" Command — Link-Based Content Analysis

**Date:** 2026-03-01
**Confidence:** High
**Decision:** Build a modular `investigate` tool as a new `hestia/investigate/` module with a 3-tier extraction pipeline (articles first, then video transcripts, then visual analysis), integrated as chat tools through the existing execution framework.

## Hypothesis

*Can Hestia support an "investigate" command where the user sends a URL (TikTok, YouTube, web article, etc.) and receives an accurate, research-quality content summary and analysis — running primarily on local hardware (Mac Mini M1, 16GB)?*

## Executive Summary

This is highly feasible. The Python ecosystem has mature, well-maintained libraries for all three content types (articles, video transcripts, audio transcription). The existing Hestia tool execution framework is purpose-built for exactly this kind of extensibility. The primary challenge is not technical capability but rather managing the complexity of multiple content types and the fragility of social media platform extraction (TikTok in particular). A phased rollout — articles first, then YouTube/video transcripts, then TikTok/audio transcription, then visual analysis — minimizes risk while delivering value quickly.

---

## SWOT Analysis

|  | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Existing tool framework (ToolRegistry, ToolExecutor) directly supports new tools. Cloud LLM integration (3-state routing) provides strong analysis capability. Council dual-path can classify "investigate" intent. M1 Mac Mini can run Whisper and vision models locally. httpx already in dependencies. | **Weaknesses:** No existing web scraping or media processing dependencies. 16GB RAM constrains simultaneous model loading (Qwen 2.5 7B + Whisper medium = ~11GB). No browser automation currently. TikTok extraction is fragile and requires cookies. |
| **External** | **Opportunities:** `trafilatura` (F1: 0.958) provides near-perfect article extraction. `youtube-transcript-api` gets YouTube captions without video download. `yt-dlp` supports 1000+ platforms. `mlx-whisper` is 2x faster than whisper.cpp on Apple Silicon. Cloud vision APIs (Gemini, GPT-4o) can analyze visual content. Ollama supports `qwen2.5vl:7b` for local vision. | **Threats:** TikTok actively blocks automated access (anti-bot, cookie requirements, CAPTCHA). Platform APIs change without notice (yt-dlp extractor breakage). Large video files consume disk temporarily. Legal gray area for scraping some platforms. Rate limiting from YouTube/TikTok. |

---

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Web article extraction (trafilatura) — immediate, reliable, high ROI. YouTube transcript extraction (youtube-transcript-api) — no video download needed, fast. LLM analysis pipeline (cloud + local) — the "brain" of the feature. | URL type detection and routing — simple regex/pattern matching. Memory integration (store investigation results) — leverage existing memory system. |
| **Low Priority** | Audio transcription pipeline (mlx-whisper) — needed for videos without captions, but most TikToks/YouTubes have them. Visual frame analysis (qwen2.5vl / cloud vision) — useful for infographics, memes, visual-only content. | Playwright for JS-heavy SPAs — rare need, heavy dependency (~50-100MB per browser context). Batch investigation (multiple URLs at once) — nice-to-have, not essential for v1. |

---

## Argue (Best Case)

### The Architecture Fits Perfectly

Hestia's tool execution framework was designed for exactly this kind of extension. The pattern is proven:
1. Create `hestia/investigate/` module following the manager pattern (`models.py`, `manager.py`, `tools.py`)
2. Register tools via `register_investigate_tools(registry)` — same pattern as `health/tools.py` and `apple/tools.py`
3. The LLM naturally decides to call `investigate_url` when the user says "investigate this link"
4. Council can classify the intent as `TOOL_USE` and route appropriately

### Article Extraction is a Solved Problem

**Trafilatura** achieves F1 0.958 on the ScrapingHub Article Extraction Benchmark. It:
- Extracts title, author, date, and clean body text from virtually any web article
- Outputs in multiple formats (text, markdown, JSON)
- Handles paywalled snippets, ads, navigation — strips everything except content
- Is actively maintained (v2.0.0 as of 2025), used by HuggingFace, IBM, Microsoft Research
- Pure Python, no browser needed, fast (~100ms per article)
- Single dependency: `pip install trafilatura`

### YouTube Transcripts are Free and Fast

**`youtube-transcript-api`** (v1.2.3, Jan 2026) provides:
- Direct access to YouTube's caption data — no video download, no API key, no auth
- Both auto-generated and manual captions
- Translation support for non-English videos
- ~100ms per transcript retrieval
- Reliability: "never failed when captions existed" in Jan 2026 testing

### TikTok Has Multiple Fallback Paths

For TikTok, there's a cascade:
1. **Best case:** TikTok auto-captions exist and can be extracted via yt-dlp metadata (no video download)
2. **Fallback 1:** Download audio only via yt-dlp, transcribe locally with mlx-whisper (~2 min for 1 min video on M1)
3. **Fallback 2:** Use Supadata or similar transcript API (paid, but reliable)
4. **Fallback 3:** Download video, extract keyframes, analyze with vision model

### Local Analysis is Powerful Enough

With cloud routing `enabled_smart` or `enabled_full`:
- Cloud LLMs (Claude, GPT-4, Gemini) can analyze long-form text with high accuracy
- Gemini 2.5 Pro handles 1M+ token contexts — entire articles or long transcripts fit easily
- Even locally, Qwen 2.5 7B can summarize and analyze 4K-8K token articles effectively

### The M1 Can Handle It

Memory budget analysis for simultaneous operation:
- Qwen 2.5 7B (already running): ~5GB
- mlx-whisper medium model: ~1.5GB
- Trafilatura processing: ~50MB
- Total: ~6.5GB, leaving ~9.5GB for OS and other processes
- Vision model (qwen2.5vl:7b) would require swapping out the text model, but Ollama handles this

### Evidence of Success

Multiple open-source projects have built similar pipelines:
- **tiktok-processor** (GitHub): Download, transcribe, and summarize TikToks with AI
- **Open Deep Research** (LangChain): Multi-agent web research with content extraction
- **Local Deep Research**: Fully local research pipeline with open-source LLMs
- **Clawdbot AI**: Browser automation + content extraction + AI analysis

---

## Refute (Devil's Advocate)

### TikTok is a Moving Target

TikTok's anti-bot measures are aggressive and unpredictable:
- yt-dlp's TikTok extractor breaks regularly (multiple GitHub issues in late 2025/early 2026)
- Cookie-based auth is fragile — cookies expire, CAPTCHAs block automated access
- Private/age-restricted content may be completely inaccessible
- On a headless Mac Mini server, there's no browser to extract cookies from
- The TikTok USDS/Oracle transition (2026) has changed data handling policies

**Mitigation:** Accept TikTok as "best-effort" with graceful degradation. If extraction fails, return a clear error message rather than crashing. Offer manual transcript paste as fallback.

### Dependency Bloat

Each content type adds dependencies:
- `trafilatura` + dependencies: ~15MB
- `yt-dlp`: ~40MB (supports 1000+ extractors, most unused)
- `mlx-whisper` + model: ~1.6GB (medium model)
- `playwright` (if needed for JS sites): ~200MB + browser binaries
- `youtube-transcript-api`: ~1MB

Total new dependencies could exceed 2GB if all features are enabled.

**Mitigation:** Make features opt-in via config. Don't require all dependencies at install time. Use lazy imports.

### Temporary File Management

Video/audio downloads create temporary files that must be cleaned up:
- A 3-minute TikTok video: ~20-50MB
- A 10-minute YouTube video (audio only): ~10-20MB
- Whisper processing requires the full audio file on disk

**Mitigation:** Use Python's `tempfile` with automatic cleanup. Set a configurable max file size limit. Clean up in `finally` blocks.

### Legal and Ethical Considerations

- Web scraping exists in a legal gray area in many jurisdictions
- TikTok's Terms of Service explicitly prohibit automated scraping
- YouTube's ToS similarly restrict automated access
- DMCA implications for downloading/transcribing copyrighted content

**Mitigation:** This is for personal research use on a personal device. Frame it as "content analysis" not "content downloading." Don't store downloaded media. Process and discard. Similar to how a browser renders and discards page content.

### Accuracy Concerns for Visual-Only Content

Some TikToks and videos are primarily visual (cooking demos, dance, fashion, art) with minimal or no speech. For these:
- Transcript extraction yields nothing useful
- Frame analysis via vision models is imprecise for nuanced visual content
- OCR on text overlays may miss context

**Mitigation:** When no transcript is available, use vision analysis on keyframes. Be transparent about analysis limitations. Include a confidence indicator in the response.

### Qwen 2.5 7B May Not Be Sufficient for Deep Analysis

The local model is good for summarization but may struggle with:
- Nuanced analysis of complex articles
- Cross-referencing claims with knowledge
- Detecting misinformation or bias
- Multi-step reasoning about content

**Mitigation:** This is already addressed by the 3-state cloud routing. When cloud is `enabled_smart` or `enabled_full`, the analysis step uses Claude/GPT-4/Gemini. For `disabled` mode, accept simpler analysis.

---

## Third-Party Evidence

### What Succeeded

1. **Perplexity AI** — Built a multi-billion-dollar business on link-based content analysis. Their architecture: extract content from URLs, feed to LLM, produce cited summaries. Validates the core value proposition.

2. **Fabric by Daniel Miessler** — Open-source CLI that pipes web content through LLM patterns. Uses `yt-dlp` + Whisper for video content. Thousands of GitHub stars. Proves the yt-dlp + Whisper + LLM pipeline works in practice.

3. **OpenAI's ChatGPT web browsing** — Uses a similar approach (fetch page content, extract text, feed to model). Validates that LLM-based content analysis produces useful results.

4. **Arc Browser's "Browse for me"** — Extracts article content and generates summaries. Shows this feature has consumer demand.

### What Failed or Struggled

1. **Direct TikTok scraping tools** — Multiple projects abandoned due to constant breakage from TikTok's anti-bot measures. `pyktok` requires a logged-in browser session.

2. **Whisper hallucination on silent segments** — Known issue where Whisper generates fabricated text during silence. Requires post-processing to detect and filter.

3. **Generic web scraping for SPAs** — Simple HTTP requests fail on React/Vue/Angular apps. Playwright/Selenium add significant complexity and resource overhead.

### Alternative Approaches Considered

1. **Browser extension approach** — Have the user's browser extract content and send it to Hestia. More reliable but requires a browser extension (adds iOS/macOS development scope).

2. **API-first approach** — Use paid APIs (Supadata, Apify) for all extraction. More reliable but adds recurring cost and external dependency.

3. **Screenshot + vision approach** — Take screenshots of pages and use vision models to "read" them. Works universally but loses text fidelity and is slow.

4. **Manual paste approach** — User copies content and pastes it into chat. Zero technical complexity but terrible UX.

**Recommendation:** Hybrid approach. Use free local extraction first, fall back to manual paste for failures. Consider paid APIs as a future enhancement if specific platforms become unreliable.

---

## Recommendation

### Architecture: New `hestia/investigate/` Module

```
hestia/investigate/
    __init__.py
    models.py          # InvestigationRequest, InvestigationResult, ContentType enum
    extractors.py      # URL-type-specific content extraction
    analyzer.py        # LLM analysis pipeline
    manager.py         # InvestigateManager (singleton, async factory)
    tools.py           # Tool definitions for ToolRegistry
    config/
        investigate.yaml  # Timeouts, model preferences, enabled extractors
```

### Content Extraction Pipeline

```
URL Input
    |
    v
URL Classifier (regex-based)
    |
    +-- Web Article --> trafilatura --> clean text
    |
    +-- YouTube --> youtube-transcript-api --> timestamped transcript
    |                   (fallback: yt-dlp audio + mlx-whisper)
    |
    +-- TikTok --> yt-dlp metadata/captions --> text
    |                (fallback: yt-dlp audio + mlx-whisper)
    |                (fallback: keyframe extraction + vision model)
    |
    +-- Other Video (Vimeo, etc.) --> yt-dlp audio + mlx-whisper
    |
    +-- Unknown --> trafilatura (try article extraction)
    |                (fallback: Playwright render + extract)
    |
    v
Extracted Content (text, metadata)
    |
    v
LLM Analysis (via existing inference pipeline)
    |
    +-- Summarize
    +-- Extract key claims/arguments
    +-- Identify sources/evidence
    +-- Note potential biases
    +-- Generate research notes
    |
    v
Investigation Result (stored in memory, returned to user)
```

### Tool Definitions

Two tools registered with the execution framework:

1. **`investigate_url`** — Primary tool. Takes a URL, extracts content, analyzes it, returns structured analysis.
   - Parameters: `url` (required), `depth` (optional: "summary" | "detailed" | "deep"), `focus` (optional: specific aspect to investigate)
   - Category: "research"
   - Timeout: 120s (video transcription can be slow)

2. **`investigate_compare`** — Comparison tool. Takes 2+ URLs, extracts all, produces comparative analysis.
   - Parameters: `urls` (required, array), `comparison_criteria` (optional)
   - Category: "research"

### Phased Implementation

**Phase 1 (Low effort, ~4-6 hours): Web Articles + YouTube Transcripts**
- New dependencies: `trafilatura`, `youtube-transcript-api`
- Covers ~80% of use cases
- No heavy dependencies (no Whisper, no Playwright, no yt-dlp)
- New tests: ~40-50

**Phase 2 (~4-6 hours): Video Audio Transcription**
- New dependencies: `yt-dlp`, `mlx-whisper` (or `openai-whisper`)
- Enables TikTok and arbitrary video support
- Requires temp file management
- New tests: ~20-30

**Phase 3 (~3-4 hours): Visual Analysis**
- New dependency: `qwen2.5vl:7b` via Ollama (or cloud vision API)
- Keyframe extraction from video
- Useful for visual-heavy content without speech
- New tests: ~15-20

**Phase 4 (~2-3 hours): Enhanced Features**
- Investigation memory (store results, cross-reference)
- Comparison mode (multiple URLs)
- iOS/macOS share sheet integration (receive links from other apps)
- Batch investigation

### Estimated Costs

| Item | One-time | Recurring |
|------|---------|-----------|
| Development time | ~15-20 hours across phases | 1-2 hours/month maintenance |
| New dependencies (disk) | ~60MB (Phase 1), ~2GB (Phase 2) | None |
| Cloud API usage (analysis) | None | ~$0.01-0.05 per investigation |
| mlx-whisper model download | ~1.5GB | None |

### Configuration

```yaml
# config/investigate.yaml
investigate:
  enabled: true

  extractors:
    articles:
      enabled: true
      timeout: 30
    youtube:
      enabled: true
      timeout: 30
      prefer_manual_captions: true
    tiktok:
      enabled: true
      timeout: 120
      cookie_file: null  # Optional: path to cookies.txt
    video_transcription:
      enabled: false  # Requires mlx-whisper
      model: "medium"  # tiny, base, small, medium, large
      timeout: 300
    visual_analysis:
      enabled: false  # Requires vision model
      max_frames: 5

  analysis:
    default_depth: "detailed"  # summary, detailed, deep
    max_content_length: 50000  # chars
    store_in_memory: true

  temp:
    directory: /tmp/hestia/investigate
    max_file_size_mb: 100
    cleanup_after_seconds: 300
```

### Confidence Level: High

The core functionality (articles + YouTube) is straightforward to implement with battle-tested libraries. The architecture maps cleanly onto Hestia's existing patterns. The phased approach means we ship value in Phase 1 and iterate.

### What Would Change This Recommendation

- If TikTok is the *primary* use case (not one of several), I'd prioritize paid API integration over local extraction, because local TikTok extraction is the least reliable path
- If the Mac Mini's 16GB RAM becomes a constraint (Qwen 2.5 7B + Whisper + other processes), we'd need to use smaller Whisper models or offload transcription to cloud
- If Apple adds a native "content extraction" API to macOS/iOS (possible given their AI push), that would be preferable to third-party libraries

---

## Final Critiques

### The Skeptic: "Why won't this work?"

**Challenge:** TikTok extraction will break constantly. You'll spend more time maintaining the TikTok extractor than building new features.

**Response:** Fair concern. That's why TikTok is Phase 2, not Phase 1. Phase 1 (articles + YouTube) is rock-solid and covers the majority of research use cases. TikTok support is explicitly "best-effort" with graceful degradation. If yt-dlp's TikTok extractor breaks, the tool returns "Unable to extract TikTok content — try pasting the transcript manually" rather than crashing. The fragility is contained.

### The Pragmatist: "Is the effort worth it?"

**Challenge:** 15-20 hours of development for a feature that could be done by just copying text into the chat window.

**Response:** The value isn't in extraction alone — it's in the *pipeline*. Manual paste requires the user to: (1) open a browser, (2) navigate to the URL, (3) find the content, (4) copy it, (5) switch to Hestia, (6) paste it, (7) type "analyze this." The investigate command reduces this to: (1) paste URL, (2) say "investigate." That's a 5-step reduction in friction. For a personal AI assistant, reducing friction IS the product. Phase 1 alone (articles + YouTube) is ~4-6 hours for the highest-value 80% of use cases. That's an excellent ROI.

### The Long-Term Thinker: "What happens in 6 months?"

**Challenge:** YouTube and TikTok will tighten their anti-scraping measures. Trafilatura may fall behind as web standards evolve. New content platforms will emerge.

**Response:** The modular architecture (URL classifier -> extractor -> analyzer) makes it easy to swap extractors without touching the analysis pipeline. `trafilatura` has been actively maintained since 2019 and is used by major institutions — it evolves with the web. For platform-specific extractors, yt-dlp has a massive contributor community that keeps pace with platform changes. The real long-term play is that as local LLM capabilities improve (vision, audio), the "download and analyze locally" approach becomes *more* reliable over time, not less. The trend is toward more capable local models, not less.

---

## Open Questions

1. **Cookie management for TikTok:** How should Hestia handle TikTok authentication? Options: (a) user provides cookies.txt manually, (b) Hestia has a headless browser that maintains a session, (c) skip auth-required content. Recommendation: (a) for v1.
2. **Memory integration depth:** Should investigation results be stored as full memory chunks (searchable, decayable) or as lightweight references? Recommendation: store summary + key findings as memory, link to full analysis in data/.
3. **iOS share sheet:** Should the iOS app register as a share target so users can share links directly from Safari/TikTok/YouTube? High UX value but requires iOS development. Defer to Phase 4.
4. **Rate limiting strategy:** How aggressively should Hestia extract content? Need to balance speed with not getting IP-blocked. Recommendation: 1-second delay between consecutive extractions, respect robots.txt.
5. **Content length limits:** Very long articles or video transcripts could exceed LLM context windows. Recommendation: chunk long content and summarize progressively, or use Gemini 2.5 Pro's 1M context for `enabled_full` mode.

---

## Sources

- [Trafilatura Documentation & Evaluation](https://trafilatura.readthedocs.io/en/latest/evaluation.html)
- [Trafilatura GitHub](https://github.com/adbar/trafilatura)
- [youtube-transcript-api PyPI](https://pypi.org/project/youtube-transcript-api/)
- [youtube-transcript-api GitHub](https://github.com/jdepoix/youtube-transcript-api)
- [yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp)
- [yt-dlp TikTok Extractor Source](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/tiktok.py)
- [Supadata TikTok Transcript API](https://supadata.ai/tiktok-transcript-api)
- [whisper.cpp GitHub](https://github.com/ggml-org/whisper.cpp)
- [mlx-whisper vs whisper.cpp Benchmark (Jan 2026)](https://notes.billmill.org/dev_blog/2026/01/updated_my_mlx_whisper_vs._whisper.cpp_benchmark.html)
- [Whisper Performance on Apple Silicon Benchmarks](https://www.voicci.com/blog/apple-silicon-whisper-performance.html)
- [mac-whisper-speedtest GitHub](https://github.com/anvanvan/mac-whisper-speedtest)
- [Lightning Whisper MLX](https://github.com/mustafaaljadery/lightning-whisper-mlx)
- [Ollama Vision Models](https://ollama.com/search?c=vision)
- [Qwen2.5-VL on Ollama](https://ollama.com/library/qwen2.5vl)
- [LangChain Open Deep Research](https://github.com/langchain-ai/open_deep_research)
- [tiktok-processor GitHub](https://github.com/rshaw5/tiktok-processor)
- [Playwright Web Scraping with Python](https://scrapfly.io/blog/posts/web-scraping-with-playwright-and-python)
- [Scraping Web Page Content Comparison](https://www.justtothepoint.com/code/scrape/)
- [ScrapingHub Article Extraction Benchmark](https://github.com/scrapinghub/article-extraction-benchmark)
- [yt-dlp TikTok Cookie Issues (GitHub #12045)](https://github.com/yt-dlp/yt-dlp/issues/12045)
- [YouTube Transcript API Developer Guide (Feb 2026)](https://medium.com/@volods/how-to-get-youtube-transcripts-a-complete-developers-guide-b3f092eb0a96)
- [Choosing Whisper Variants (Modal)](https://modal.com/blog/choosing-whisper-variants)
- [Video-MME Benchmark (CVPR 2025)](https://github.com/MME-Benchmarks/Video-MME)
- [Personal AI Infrastructure by Daniel Miessler](https://github.com/danielmiessler/Personal_AI_Infrastructure)
