"""
AI content generation for wiki articles.

Uses CloudInferenceClient to generate narrative architecture
documentation — overview, module deep dives, and diagrams.
"""

from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.inference.client import Message

from .models import WikiArticle, ArticleType, GenerationStatus
from .scanner import WikiScanner


# =============================================================================
# System Prompts
# =============================================================================

OVERVIEW_SYSTEM_PROMPT = """You are writing the architecture overview for Hestia, a locally-hosted personal AI assistant built by a single developer (Andrew) over ~15 sessions. Write as if you're a master craftsman giving a tour of your workshop to someone who built it but wants to fall in love with it again.

Be specific — name files, patterns, actual design choices. No hand-waving. Cover:
1. What Hestia is and why it exists (2-3 paragraphs)
2. The layer architecture and how data flows through it
3. The three modes (Tia/Mira/Olly) and personality system
4. Key technical decisions that make it distinctive
5. The security posture and why it matters for a personal AI
6. What makes this codebase cohesive despite being built incrementally

Write ~2000 words in markdown. Use ## headings. Be warm but precise."""

MODULE_SYSTEM_PROMPT = """You are writing a field guide entry for one module of Hestia, a locally-hosted personal AI assistant. Write for a developer who built this system but wants to understand each part deeply.

Structure your entry exactly as:

## [Module Name]
*[One-line subtitle]*

### What It Does
Two sentences. Be concrete.

### Why It Exists
The problem this module solves. What would break without it.

### Key Files
One line per file. Format: `filename.py` — what it does.

### How It Connects
Upstream dependencies (what feeds into this module) and downstream consumers (what uses its output).

### What's Clever
The non-obvious design decisions. Patterns that aren't immediately apparent from reading the code.

### Closing Thought
One sentence that makes this module feel essential, not incidental.

Write ~400 words. Be specific about actual code, not generic descriptions."""

DIAGRAM_SYSTEM_PROMPT = """You are generating Mermaid diagram source code for Hestia's architecture documentation. Output ONLY valid Mermaid syntax — no markdown fences, no explanatory text.

Use dark-theme-friendly colors. Keep diagrams readable with clear labels. Use the actual module and file names from the codebase."""


class WikiGenerator:
    """
    Generates wiki article content via cloud LLM.

    Uses CloudInferenceClient.complete() directly, same pattern
    as council's _call_cloud. Falls back gracefully if cloud
    is not available.
    """

    def __init__(self, scanner: Optional[WikiScanner] = None):
        """
        Initialize generator.

        Args:
            scanner: WikiScanner for reading source files.
        """
        self.scanner = scanner or WikiScanner()
        self.logger = get_logger()

    async def generate_overview(self) -> WikiArticle:
        """
        Generate the architecture overview article.

        Uses CLAUDE.md as source context.

        Returns:
            WikiArticle with generated content.
        """
        source = self.scanner.get_project_overview_source()
        if not source:
            return WikiArticle.create(
                article_type=ArticleType.OVERVIEW,
                title="Architecture Overview",
                subtitle="How Hestia works",
                generation_status=GenerationStatus.FAILED,
            )

        source_hash = self.scanner.get_overview_hash()

        messages = [
            Message(
                role="user",
                content=f"Here is the project context for Hestia:\n\n{source}\n\nWrite the architecture overview.",
            ),
        ]

        content = await self._call_cloud(
            messages=messages,
            system=OVERVIEW_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=4096,
        )

        if content is None:
            return WikiArticle.create(
                article_type=ArticleType.OVERVIEW,
                title="Architecture Overview",
                subtitle="How Hestia works",
                generation_status=GenerationStatus.FAILED,
            )

        return WikiArticle.create(
            article_type=ArticleType.OVERVIEW,
            title="Architecture Overview",
            subtitle="How Hestia works",
            content=content,
            source_hash=source_hash,
            generation_status=GenerationStatus.COMPLETE,
        )

    async def generate_module(self, module_name: str, display_name: str, subtitle: str = "") -> WikiArticle:
        """
        Generate a module deep dive article.

        Args:
            module_name: Module directory name (e.g., "memory").
            display_name: Human-readable name (e.g., "Memory Layer").
            subtitle: Short description.

        Returns:
            WikiArticle with generated content.
        """
        source = self.scanner.get_module_source(module_name)
        if not source:
            return WikiArticle.create(
                article_type=ArticleType.MODULE,
                title=display_name,
                subtitle=subtitle,
                module_name=module_name,
                generation_status=GenerationStatus.FAILED,
            )

        source_hash = self.scanner.get_module_hash(module_name)

        messages = [
            Message(
                role="user",
                content=f"Here are the key source files for the {display_name} module:\n\n{source}\n\nWrite the field guide entry.",
            ),
        ]

        content = await self._call_cloud(
            messages=messages,
            system=MODULE_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=2048,
        )

        if content is None:
            return WikiArticle.create(
                article_type=ArticleType.MODULE,
                title=display_name,
                subtitle=subtitle,
                module_name=module_name,
                generation_status=GenerationStatus.FAILED,
            )

        return WikiArticle.create(
            article_type=ArticleType.MODULE,
            title=display_name,
            subtitle=subtitle,
            content=content,
            module_name=module_name,
            source_hash=source_hash,
            generation_status=GenerationStatus.COMPLETE,
        )

    async def generate_diagram(self, diagram_type: str) -> WikiArticle:
        """
        Generate a Mermaid diagram.

        Args:
            diagram_type: One of "architecture", "request-lifecycle", "data-flow".

        Returns:
            WikiArticle with Mermaid source as content.
        """
        overview_source = self.scanner.get_project_overview_source()

        prompts = {
            "architecture": "Generate a Mermaid flowchart (graph TD) showing Hestia's system architecture. Show the major layers: iOS App → API (FastAPI) → Orchestration → {Inference, Memory, Execution, Council} → {Ollama, Cloud, ChromaDB, SQLite, Apple Tools}. Include the security layer wrapping everything.",
            "request-lifecycle": "Generate a Mermaid sequence diagram showing the lifecycle of a chat request through Hestia. Show: iOS → API → Auth Middleware → RequestHandler → Council (intent classification) → InferenceClient (model routing) → Response. Include the memory retrieval and tool execution branches.",
            "data-flow": "Generate a Mermaid flowchart (graph LR) showing data flow in Hestia. Show: User Input → Orchestration → Memory Search → Context Assembly → Inference → Tool Detection → Tool Execution → Response Assembly → Memory Staging → User Output.",
        }

        prompt = prompts.get(diagram_type, prompts["architecture"])

        messages = [
            Message(
                role="user",
                content=f"Project context:\n\n{overview_source[:4000]}\n\n{prompt}",
            ),
        ]

        content = await self._call_cloud(
            messages=messages,
            system=DIAGRAM_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=2048,
        )

        titles = {
            "architecture": "System Architecture",
            "request-lifecycle": "Request Lifecycle",
            "data-flow": "Data Flow",
        }
        subtitles = {
            "architecture": "How the layers connect",
            "request-lifecycle": "A chat message's journey",
            "data-flow": "Where data lives and moves",
        }

        if content is None:
            return WikiArticle.create(
                article_type=ArticleType.DIAGRAM,
                title=titles.get(diagram_type, diagram_type),
                subtitle=subtitles.get(diagram_type, ""),
                module_name=diagram_type,
                generation_status=GenerationStatus.FAILED,
            )

        # Strip markdown fences if the model wrapped them
        content = content.strip()
        if content.startswith("```mermaid"):
            content = content[len("```mermaid"):].strip()
        if content.startswith("```"):
            content = content[3:].strip()
        if content.endswith("```"):
            content = content[:-3].strip()

        return WikiArticle.create(
            article_type=ArticleType.DIAGRAM,
            title=titles.get(diagram_type, diagram_type),
            subtitle=subtitles.get(diagram_type, ""),
            content=content,
            module_name=diagram_type,
            source_hash=self.scanner.get_overview_hash(),
            generation_status=GenerationStatus.COMPLETE,
        )

    async def _call_cloud(
        self,
        messages: List[Message],
        system: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> Optional[str]:
        """
        Call cloud LLM for content generation.

        Uses the same pattern as council's _call_cloud — direct
        call through InferenceClient bypassing the router.

        Returns:
            Generated text content, or None if cloud unavailable.
        """
        try:
            from hestia.inference.client import get_inference_client

            client = get_inference_client()
            response = await client._call_cloud(
                messages=messages,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            self.logger.info(
                "Wiki content generated via cloud",
                component=LogComponent.WIKI,
                data={
                    "tokens_in": response.tokens_in,
                    "tokens_out": response.tokens_out,
                    "model": response.model,
                },
            )

            return response.content

        except Exception as e:
            self.logger.warning(
                f"Wiki generation failed: {type(e).__name__}",
                component=LogComponent.WIKI,
                data={"detail": str(e)[:200]},
            )
            return None
