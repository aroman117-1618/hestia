"""
Data models for the verification pipeline.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class HallucinationRisk(Enum):
    """Risk level assigned by the verification pipeline."""
    NONE = "none"                  # All checks passed
    TOOL_BYPASS = "tool_bypass"    # Response claims domain data without a tool call
    LOW_RETRIEVAL = "low_retrieval"  # Retrieved context had low similarity score
    SLM_FLAG = "slm_flag"          # SLM Validator detected ungrounded claims
    UNKNOWN = "unknown"            # Verification failed internally (fail-open)


@dataclass
class VerificationResult:
    """Result of the full verification pipeline for a single response."""
    risk: HallucinationRisk = HallucinationRisk.NONE
    disclaimer: Optional[str] = None       # Appended to response if non-None
    flags: List[str] = field(default_factory=list)  # Human-readable flag list
    retrieval_score: Optional[float] = None         # Top cosine similarity from memory search
    slm_checked: bool = False                        # Whether SLM Validator ran

    @property
    def has_risk(self) -> bool:
        return self.risk != HallucinationRisk.NONE

    @classmethod
    def clean(cls) -> "VerificationResult":
        return cls(risk=HallucinationRisk.NONE)
