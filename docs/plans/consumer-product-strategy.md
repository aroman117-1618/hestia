# Consumer Product Strategy: Local-First AI Life Assistant

**Author:** Andrew Roman + Claude
**Date:** 2026-03-19
**Status:** DRAFT — Brainstorm & Strategic Planning
**Revenue Target:** $10–15k/month within 12–18 months of launch

---

## 1. Vision

A private, local-first AI assistant that actually *manages your life* — not just answers questions. It connects to your Apple and Google ecosystems, learns your patterns, remembers context across conversations, and takes action on your behalf. Everything runs on your hardware. Your data never leaves your machine unless you explicitly opt into cloud models for enhanced capability.

**One-liner:** "Your AI. Your machine. Your life — managed."

### What This Is NOT

- Not another chatbot wrapper (ChatGPT, Gemini, Copilot already exist)
- Not a developer tool (LangChain, AutoGPT target engineers)
- Not a home automation hub (Home Assistant owns that)
- Not a local LLM runner (Ollama, Jan AI, LM Studio are commodity)

### What This IS

The missing layer between "I can run a local AI model" and "I have an AI that actually runs my life." The orchestration, memory, tool execution, and ecosystem integration that turns a language model into a competent personal agent.

---

## 2. Target Audience

**Primary: Privacy-conscious professionals ($39–49/mo willingness to pay)**

- Lawyers, therapists, financial advisors, healthcare workers, executives
- Handle sensitive client/patient information daily
- Cannot use cloud AI for professional work (compliance, ethics, liability)
- Value time savings — an hour saved daily is worth hundreds in billable time
- Comfortable paying for quality tools (already pay for practice management, etc.)

**Secondary: Productivity-focused knowledge workers ($19–29/mo)**

- Small business owners, consultants, solo founders, remote workers
- Drowning in calendar, email, task management across multiple tools
- Want automation but don't trust Big Tech with everything
- Less price-sensitive than consumers, more than enterprises

**Tertiary (growth market): Tech-forward families**

- Shared household calendar/task management
- Health tracking and wellness coaching
- Privacy-conscious parents who don't want Alexa/Siri surveillance
- Lower willingness to pay individually, but interesting for "family plan" tier

### User Persona: "Sarah the Attorney"

Sarah runs a 3-person law firm. She juggles 40+ active cases, each with deadlines, client communications, and court dates. She can't use ChatGPT for case research because client privilege. She currently spends 2 hours/day on calendar management, email triage, and task tracking. She'd pay $49/month without blinking for an AI that handles her inbox prioritization, deadline tracking, and daily briefings — all running on her office Mac.

### User Persona: "Marcus the Consultant"

Marcus is an independent management consultant. He tracks 6 client engagements across Google Calendar, Gmail, and a dozen spreadsheets. He wants AI that can prepare meeting briefs, summarize email threads, and remind him of commitments — but he doesn't want his client data on OpenAI's servers. He's comfortable with basic tech setup (installs apps, manages passwords) but not a developer.

---

## 3. Product Architecture

### 3.1 What Ships (Core Platform — Source Available / BSL 1.1)

The core platform is source-available under the Business Source License 1.1, converting to full open source after 3 years. Anyone can inspect the code, verify privacy claims, and run it for personal use.

**Core Engine (always local, always free):**

| Component | What It Does | Hestia Origin |
|-----------|-------------|---------------|
| Agent Orchestration | Multi-agent routing, confidence gating, intent classification | Council + AgentOrchestrator |
| Memory System | Long-term memory with temporal decay, importance scoring, consolidation | MemoryManager + ChromaDB |
| Tool Execution | Sandboxed tool runtime with approval workflow | ToolExecutor + Sandbox |
| Local Inference | Ollama integration, model management, auto-download | InferenceClient |
| Conversation Engine | Context-aware chat with personality and memory retrieval | RequestHandler + PromptBuilder |
| Security Layer | Encrypted credential storage, biometric auth, audit trail | CredentialManager + JWT |
| Settings & Config | GUI-based configuration (replaces YAML files) | New — consumer-friendly |
| Setup Wizard | One-click install, guided ecosystem connection | New — critical for adoption |

**Ecosystem Integrations (free tier includes 2, paid unlocks all):**

| Integration | Platforms | Hestia Origin |
|-------------|-----------|---------------|
| Calendar | Apple Calendar, Google Calendar | apple/ tools |
| Email | Apple Mail, Gmail | apple/ tools + New |
| Tasks/Reminders | Apple Reminders, Google Tasks | apple/ tools + New |
| Notes | Apple Notes, Google Keep | apple/ tools + New |
| Contacts | Apple Contacts, Google Contacts | apple/ tools + New |
| Health | Apple HealthKit, Google Fit | health/ module |
| Files | iCloud Drive, Google Drive | files/ module + New |

### 3.2 Premium Features (Subscription — $39/mo or $29/mo annual)

| Feature | Description | Hestia Origin |
|---------|-------------|---------------|
| Unlimited Integrations | All 7 ecosystem integrations unlocked | — |
| Cloud Model Access | Route to Claude, GPT-4, Gemini for complex tasks | cloud/ module |
| Daily Briefings | Proactive morning brief of calendar, priorities, health | proactive/ module |
| Smart Inbox | AI-prioritized email with action suggestions | inbox/ module |
| Health Coaching | Personalized wellness insights from health data | health/ coaching |
| Knowledge Graph | Persistent entity/fact memory across conversations | research/ module |
| Multi-Device Sync | Access from phone + desktop (local network) | API + iOS app |
| Priority Updates | Early access to new features and models | — |

### 3.3 Add-On Modules (Separate purchase or higher tier)

| Module | Price | Description | Hestia Origin |
|--------|-------|-------------|---------------|
| Trading Desk | $19/mo | Autonomous crypto + stock trading with risk management | trading/ module |
| Research Agent | $9/mo | Deep web research, YouTube analysis, knowledge synthesis | investigate/ + research/ |
| Voice Journal | $9/mo | Voice memo transcription + pattern analysis + journaling | voice/ module |
| News Intelligence | $9/mo | Personalized news aggregation with source tracking | newsfeed/ module |

---

## 4. Licensing & Legal

### Business Source License 1.1

- **Source available:** Code is public on GitHub, anyone can read and audit
- **Personal use:** Free and unrestricted
- **Commercial restriction:** Cannot sell a competing hosted service using the code
- **Change date:** 3 years — after which each version converts to Apache 2.0
- **Additional Use Grant:** Small businesses (<$1M revenue) can use freely

This follows the precedent set by HashiCorp (Terraform), Sentry, CockroachDB, and MariaDB. It maximizes trust (verifiable privacy), discoverability (public GitHub repo), and community goodwill while protecting commercial revenue.

### Why This Matters for Our Audience

Privacy-conscious professionals won't trust a closed-source "we promise your data is private" claim. Source-available lets their IT person (or a security auditor) verify the claim. This is a competitive advantage, not a vulnerability.

---

## 5. Genericization Roadmap: Hestia → Consumer Product

### Phase 1: Decouple & Abstract (Weeks 1–4)

The goal is to separate "platform" from "Andrew's personal assistant."

| Task | Effort | Description |
|------|--------|-------------|
| Extract personal config | S | Move all Andrew-specific settings (Mac Mini IP, Tailscale, device IDs) to user-profile layer |
| Abstract Apple tools | M | Generalize the 20 Apple tools from hardcoded paths to configurable endpoints |
| Build Google integration layer | L | Mirror Apple tool capabilities for Google ecosystem (Calendar, Gmail, Tasks, Keep, Contacts, Drive, Fit) |
| Create setup wizard | L | First-run experience: model download, ecosystem auth, personality config |
| Replace YAML with GUI config | M | Settings UI that writes config files — user never sees YAML |
| Strip internal references | S | Remove all Hestia/Artemis/Apollo naming, internal jokes, Andrew-specific context |
| Rebrand codebase | S | New public name throughout (placeholder: `[PROJECT_NAME]`) |

### Phase 2: Consumer UX (Weeks 5–8)

| Task | Effort | Description |
|------|--------|-------------|
| One-click installer | L | macOS .dmg / Windows .exe / Linux AppImage with bundled Ollama |
| Onboarding flow | L | 5-step wizard: install → model download → ecosystem connect → first conversation → first "wow moment" |
| Desktop app (Electron or native) | L | Tray icon, quick-access chat window, notification integration |
| Mobile companion | M | Lightweight iOS/Android app that connects to local server over LAN/Tailscale |
| Error recovery | M | User-friendly error messages, auto-restart, health monitoring |
| Usage analytics (opt-in) | S | Anonymous telemetry for product decisions (with clear opt-out) |

### Phase 3: Monetization Infrastructure (Weeks 9–12)

| Task | Effort | Description |
|------|--------|-------------|
| License key system | M | Simple key-based activation for premium features |
| Payment integration | M | Stripe subscription management |
| Cloud model proxy | M | Managed API key relay (user pays us, we handle cloud model costs) |
| Feature gating | M | Clean free/premium split without crippling the free experience |
| Update system | M | Auto-update mechanism with changelog |
| Billing portal | S | Self-service subscription management |

### Phase 4: Launch & Growth (Weeks 13–20)

| Task | Effort | Description |
|------|--------|-------------|
| Landing page | M | Product website with clear value prop, demo video, pricing |
| Documentation | L | User guides, setup tutorials, FAQ, troubleshooting |
| Community infrastructure | M | Discord/forum, GitHub discussions, bug reporting |
| Content marketing | Ongoing | Blog posts, YouTube demos, Reddit/HN engagement |
| Beta program | M | 50–100 early users for feedback before public launch |
| Launch | — | Product Hunt, Hacker News, relevant subreddits, indie hacker communities |

---

## 6. Revenue Model & Path to $10–15k/month

### Pricing Tiers

| Tier | Price | What's Included |
|------|-------|-----------------|
| **Free** | $0 | Core engine + 2 integrations + local models only |
| **Pro** | $29/mo ($290/yr) | All integrations + cloud models + briefings + smart inbox + knowledge graph |
| **Pro+** | $49/mo ($490/yr) | Everything in Pro + health coaching + multi-device + priority updates |
| **Add-ons** | $9–19/mo each | Trading Desk, Research Agent, Voice Journal, News Intelligence |

### Revenue Math

| Scenario | Users | Mix | Monthly Revenue |
|----------|-------|-----|-----------------|
| Conservative | 400 | 60% Pro, 30% Pro+, 10% add-ons | ~$12,600/mo |
| Moderate | 300 | 50% Pro, 40% Pro+, 20% add-ons | ~$12,900/mo |
| Optimistic | 250 | 40% Pro, 50% Pro+, 30% add-ons | ~$13,500/mo |

**Key insight:** You don't need viral growth. 300–400 paying users at healthy ARPU gets you to target. This is a "1,000 true fans" business.

### Cost Structure (Estimated)

| Item | Monthly Cost | Notes |
|------|-------------|-------|
| Cloud model API costs | $500–2,000 | Passed through at ~20% margin or included in Pro |
| Stripe fees | 2.9% + $0.30 | ~$400 at $13k revenue |
| Infrastructure (landing page, CDN, email) | $50–100 | Minimal — product runs on user hardware |
| Apple Developer Program | $8.25 | $99/year |
| Domain + DNS | $5 | Annual, amortized |
| **Total overhead** | ~$1,000–2,500 | |
| **Net to Andrew** | ~$10,000–12,500 | At $13k gross |

The beauty of local-first: your COGS are tiny. No servers to run. No GPU fleet. Users provide their own compute.

---

## 7. Competitive Positioning

### Direct Competitors

| Product | What They Do | Our Advantage |
|---------|-------------|---------------|
| Jan AI | Local LLM chat UI | No ecosystem integrations, no agent capabilities, no memory |
| Ollama + Open WebUI | Local model runner + web chat | Chatbot only — no calendar, email, tasks, health, or proactive features |
| Nextcloud AI | Self-hosted AI inside Nextcloud | Tied to Nextcloud ecosystem — no Apple/Google integration |
| Apple Intelligence | On-device AI features | Locked to Apple, limited capabilities, no extensibility, no local models |
| Google Gemini | Cloud AI assistant | All data goes to Google, no local option, no customization |
| ChatGPT | General AI chatbot | Cloud-only, no deep ecosystem integration, no persistent memory, no agent actions |

### Our Moat (things that are hard to replicate)

1. **Deep dual-ecosystem integration.** 14+ tools across Apple AND Google. Nobody else does both.
2. **Agent architecture.** Multi-agent orchestration with confidence gating isn't a weekend project.
3. **Memory system.** Temporal decay, importance scoring, consolidation, and pruning. This is what makes the AI feel like it *knows* you vs. starting fresh every conversation.
4. **Privacy-verifiable.** Source-available code means the privacy claim is auditable, not marketing.
5. **Local-first economics.** No server costs means margin stays high as you scale.

---

## 8. Go-to-Market Strategy

### Pre-Launch (Month 1–3)

- Build in public: regular dev updates on Twitter/X, blog, YouTube
- Share architecture decisions and technical deep-dives (content marketing)
- Collect email waitlist on landing page
- Engage in r/selfhosted, r/LocalLLaMA, r/privacy, Hacker News
- Identify 20–30 beta users from target personas

### Beta (Month 4–5)

- Private beta with 50–100 users
- Weekly feedback calls with 5–10 users
- Iterate on onboarding (this is make-or-break)
- Document setup success rate — target >80% complete setup in <15 minutes

### Launch (Month 6)

- Product Hunt launch
- Hacker News "Show HN" post
- Blog post: "Why I Built a Local AI That Manages My Life"
- Reddit posts in relevant communities
- Direct outreach to tech journalists covering AI/privacy

### Growth (Month 7+)

- SEO-optimized content (tutorials, comparisons, "best local AI" articles)
- YouTube demos showing real workflows (calendar management, email triage, health coaching)
- Referral program (1 month free for referrer + referee)
- Integration partnerships (Obsidian, Notion, Todoist — premium add-ons)
- Conference talks at indie hacker and privacy-focused events

---

## 9. Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Apple/Google API changes break integrations | High | Abstract integration layer with versioned adapters; monitor API changelogs |
| Local models get good enough that "just Ollama" satisfies most people | Medium | Our value isn't the model — it's the orchestration, memory, and integrations. Models are commodity; the system isn't. |
| Big tech ships competing features (Apple Intelligence gets better) | Medium | Apple/Google will never open-source or let you cross ecosystems. We do both. |
| Support burden overwhelms a solo developer | High | Invest heavily in docs, automated diagnostics, community forums. Hire part-time support at $3k/mo once revenue exceeds $8k/mo. |
| BSL license creates community backlash | Low | BSL is well-established (HashiCorp, Sentry, CockroachDB). Personal use is unrestricted. 3-year change date is generous. |
| Model quality on consumer hardware disappoints | Medium | Hybrid architecture — seamless cloud fallback for complex tasks. Clearly communicate hardware requirements. |
| Onboarding friction kills conversion | Critical | This is the #1 product risk. Budget 40% of Phase 2 effort here. Test with non-technical users early and often. |

---

## 10. Success Metrics

### North Star: Monthly Recurring Revenue (MRR)

| Milestone | Target | Timeline |
|-----------|--------|----------|
| First paying user | $29–49 | Month 6 (launch) |
| $1k MRR | ~25 users | Month 8 |
| $5k MRR | ~130 users | Month 12 |
| $10k MRR | ~280 users | Month 15 |
| $15k MRR | ~400 users | Month 18 |

### Leading Indicators

- **Setup completion rate:** Target >80% (users who start install and complete first conversation)
- **Week 1 retention:** Target >60% (users active 7 days after install)
- **Free → Paid conversion:** Target >8% (industry average for freemium is 2–5%; our niche should outperform)
- **Monthly churn:** Target <5% (if we're solving real problems, people stay)
- **GitHub stars:** Vanity metric but correlates with organic discovery. Target 1,000 in first 6 months.

---

## 11. Open Questions (To Resolve Before Phase 1)

1. **Product name.** Working on this — needs to feel trustworthy, capable, slightly warm. Not another Greek god. Not another acronym.
2. **Windows support priority.** Mac-first is natural (your stack is macOS-native) but Windows users are 75% of the desktop market. When does Windows support ship?
3. **Linux support.** Self-hosted/privacy crowd skews heavily Linux. Potential early adopter goldmine or support nightmare?
4. **Google integration approach.** OAuth flow for Google APIs adds complexity. Do we build native Google integration or start with Apple-only and add Google in v2?
5. **Model recommendations.** Which models do we recommend/bundle for different hardware tiers? Need a compatibility matrix.
6. **Family/multi-user.** Is this a v1 feature or post-launch? Changes architecture significantly.
7. **Naming the agents.** Do consumers get exposed to the multi-agent architecture, or is it abstracted away as just "your assistant"?

---

## 12. Immediate Next Steps

1. **Name brainstorm session** — Land on a product name
2. **Competitive deep-dive** — Install and evaluate Jan AI, Open WebUI, and Nextcloud AI to understand exact feature gaps
3. **Architecture audit** — Inventory every Hestia component and classify as: ships in free tier, ships in premium, doesn't ship (too personal/niche), needs significant rework
4. **Google API research** — Scope effort for Google Calendar, Gmail, Tasks, Keep, Contacts, Drive, Fit integrations
5. **BSL license setup** — Draft LICENSE file, review BSL 1.1 template from MariaDB
6. **Landing page wireframe** — Even before the product is ready, start collecting waitlist emails
