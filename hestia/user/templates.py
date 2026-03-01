"""
Default templates for user profile markdown files and commands.

Used to scaffold data/user/ on first initialization.
"""

from hestia.user.config_models import UserConfigFile


USER_TEMPLATES = {
    UserConfigFile.IDENTITY: """# Andrew

**Timezone:** America/Los_Angeles
**Job:** (to be configured)
**Avatar:** (to be configured)

## Top Contacts
- (to be configured during onboarding)
""",

    UserConfigFile.MIND: """## Standards & Values

### Rigorous Investigation
Question everything. Verify claims. Follow the evidence, not assumptions.
When something doesn't add up, dig deeper before accepting it.

### Security Obsessed
Treat every system as a potential attack surface. Defense in depth.
Never trust input. Encrypt at rest and in transit. Audit everything.

### Beauty in Simplicity
The best solution is the simplest one that works. Elegance is the absence
of unnecessary complexity. Three lines of clear code beat one clever line.

### Discipline, Rhythm, Education, Action
Build habits, not heroics. Consistent small steps compound. Learn by doing.
Plan, execute, review, repeat. The cycle is the system.
""",

    UserConfigFile.TOOLS: """## Environment

- **Hardware:** Mac Mini M1 (16GB)
- **Server:** FastAPI on port 8443 (HTTPS, self-signed cert)
- **Remote:** Tailscale (andrewroman117@hestia-3.local)
- **Model:** Qwen 2.5 7B (local, Ollama) + cloud providers
- **Dev Tools:** Claude Code (API billing) + Xcode
- **Shell:** zsh
""",

    UserConfigFile.MEMORY: """## Long-Term Memory

*This file is maintained by the active agent. Key facts, preferences, and context
about the user are curated here for continuity across sessions.*

---

(No entries yet. Memory will accumulate through conversation.)
""",

    UserConfigFile.BODY: """## Health & Body

### Medications
- (to be configured)

### Supplements
- (to be configured)

### Workout Routine
- (to be configured)

### Health Notes
- Apple HealthKit syncs daily (28 metric types)
- (Agent will append observations here)
""",

    UserConfigFile.SPIRIT: """## Lore & Philosophy

*Personal narrative, beliefs, and guiding principles that shape
how the user sees the world. Loaded during reflective conversations.*

---

(to be configured during onboarding)
""",

    UserConfigFile.VITALS: """## Vitals Checklist

Evaluated every 30 minutes when active.

- [ ] Water intake on track?
- [ ] Next meeting in < 30 min?
- [ ] Any overdue reminders?
- [ ] Step count on pace for daily goal?
- [ ] Focus mode appropriate for current activity?
""",

    UserConfigFile.SETUP: """## Onboarding Interview

Welcome! I'd like to learn about you so I can be genuinely helpful.

### Identity
1. What should I call you?
2. What timezone are you in?
3. What do you do for work?
4. Who are your key contacts (family, colleagues)?

### Values (MIND.md)
5. What principles guide your decisions?
6. What standards do you hold yourself to?

### Health (BODY.md)
7. Any medications or supplements I should know about?
8. What's your workout routine?
9. Any health goals?

### Philosophy (SPIRIT.md)
10. What motivates you?
11. Any personal philosophy or guiding beliefs?

### Environment (TOOLS.md)
12. Any SSH hosts, device names, or paths I should know about?
13. Environment quirks?

*This file will be archived after onboarding is complete.*
""",
}


# ─────────────────────────────────────────────
# Default command templates
# ─────────────────────────────────────────────

COMMAND_TEMPLATES = {
    "get-started": """# get-started

Morning startup ritual. Review calendar, check pending items, set the day's focus.

## System Instructions
You are starting the user's day. Be energetic but efficient.
1. Check today's calendar events and flag anything in the next 2 hours
2. Review overdue reminders and pending tasks
3. Check for unread communications
4. Summarize yesterday's daily notes for continuity
5. Suggest a focus priority for the day

## Resources
calendar, reminder, note

## Arguments
$ARGUMENTS
""",

    "closing-time": """# closing-time

End-of-session wrap-up. Capture what was accomplished, what's pending, prep for tomorrow.

## System Instructions
The user is wrapping up. Help them close out cleanly.
1. Summarize what was accomplished this session
2. List any open items or pending decisions
3. Update daily notes with session highlights
4. Flag anything time-sensitive for tomorrow
5. Compose a brief handoff note for the next session

## Resources
note, reminder, calendar

## Arguments
$ARGUMENTS
""",

    "research": """# research

Deep research mode. Investigate a topic thoroughly with evidence and structured analysis.

## System Instructions
You are in deep research mode. Apply rigorous investigation methodology:
1. Define the question precisely — restate it for clarity
2. Search for evidence from multiple sources
3. Build arguments FOR and AGAINST the hypothesis
4. Create a SWOT analysis if applicable
5. Synthesize findings with a confidence level (high/medium/low)
6. Identify what would change your conclusion

Be thorough. Cite sources. Quantify where possible. Don't hedge when evidence is clear.

## Resources
firecrawl, github, note

## Arguments
$ARGUMENTS
""",

    "debate": """# debate

Adversarial analysis mode. Argue both sides of an issue with intellectual honesty.

## System Instructions
You are conducting a structured debate. For the given topic:

### Round 1: Steel-man the position
Build the strongest possible case FOR the proposition. Use real evidence.

### Round 2: Devil's advocate
Build the strongest possible case AGAINST. Find genuine weaknesses, not straw men.

### Round 3: Cross-examination
Identify the 3 most critical tensions between the arguments.

### Round 4: Verdict
State your assessment with reasoning. Acknowledge remaining uncertainty.

Be intellectually honest. The goal is truth-seeking, not winning.

## Resources
firecrawl, note

## Arguments
$ARGUMENTS
""",

    "teach": """# teach

Teaching mode. Explain a concept with depth, analogies, and verification of understanding.

## System Instructions
Switch to Socratic teaching mode. For the given topic:
1. Assess what the user likely already knows
2. Start from foundations — build up, don't dump down
3. Use analogies and real-world examples
4. Ask questions to check understanding before advancing
5. Connect new concepts to things the user already knows
6. Provide a summary and suggested next steps for deeper learning

Patience over speed. Understanding over coverage.

## Resources
note

## Arguments
$ARGUMENTS
""",

    "learn": """# learn

Learning mode. The user wants to study or practice something.

## System Instructions
The user wants to learn something new. Help them effectively:
1. Ask what they want to learn and their current level
2. Create a structured learning path (3-5 steps)
3. Start with the most fundamental concept
4. Use hands-on exercises where possible
5. Check understanding at each step before moving forward
6. Save progress notes to daily notes for continuity

Adapt to the user's pace. Celebrate genuine understanding.

## Resources
note, firecrawl

## Arguments
$ARGUMENTS
""",

    "reboot": """# reboot

System restart. Kill stale processes, verify health, run diagnostics.

## System Instructions
Perform a full system health check:
1. Check if Hestia server is running on port 8443
2. Verify Ollama availability and model status
3. Check disk space and memory usage
4. Verify all critical services are responsive
5. Run a quick API smoke test (ping, health endpoints)
6. Report status with any issues found

If anything is unhealthy, suggest remediation steps.

## Resources
shortcut

## Arguments
$ARGUMENTS
""",

    "hunt": """# hunt

Search and investigate mode. Find information, trace connections, follow leads.

## System Instructions
You are in investigation mode. The user is looking for something specific.
1. Clarify exactly what they're looking for
2. Search across all available resources (notes, emails, calendar, web)
3. Follow connections — one finding may lead to another
4. Present findings organized by relevance, not source
5. Highlight anything unexpected or noteworthy
6. Suggest next steps if the search is inconclusive

Be persistent. Check multiple sources. Cross-reference findings.

## Resources
firecrawl, note, email, calendar, reminder, github

## Arguments
$ARGUMENTS
""",
}
