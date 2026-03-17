"""
Hestia Verification Module — multi-layer hallucination prevention pipeline.

Layers:
  1. Tool Compliance Gate   — detects domain data claims without tool calls (zero latency)
  2. Retrieval Score Guard  — low-similarity context injects uncertainty hint (via memory.manager)
  3. SLM Validator          — qwen2.5:0.5b binary grounding check (~100ms, non-CHAT only)
  4. Logprob Entropy        — reserved for MetaMonitor metrics (Sprint 19)
"""
from hestia.verification.models import HallucinationRisk, VerificationResult
from hestia.verification.tool_compliance import ToolComplianceChecker

__all__ = ["HallucinationRisk", "VerificationResult", "ToolComplianceChecker"]
