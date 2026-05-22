"""Spec 147 — Shared contracts for the Readiness Evidence Gate.

Defines canonical claim labels, classification codes, allowed/disallowed
wording, and required evidence field names used by the gate and its tests.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Claim being evaluated by the default gate
# ---------------------------------------------------------------------------

CLAIM_CONTROLLED_DEMO_90 = "90%+ controlled demo / portfolio readiness"

# ---------------------------------------------------------------------------
# Gate classification codes
# ---------------------------------------------------------------------------

PASS_CONTROLLED_DEMO_90 = "PASS_CONTROLLED_DEMO_90"
FAIL_CONTROLLED_DEMO_90 = "FAIL_CONTROLLED_DEMO_90"
PASS_PILOT_READINESS = "PASS_PILOT_READINESS"
FAIL_PILOT_READINESS = "FAIL_PILOT_READINESS"
PRODUCTION_NOT_CLAIMED = "PRODUCTION_NOT_CLAIMED"
PRODUCTION_CLAIM_BLOCKED = "PRODUCTION_CLAIM_BLOCKED"

# ---------------------------------------------------------------------------
# Evidence artifact keys (as they appear in the gate result)
# ---------------------------------------------------------------------------

EVIDENCE_BOUNDED_VALIDATION = "bounded_validation"
EVIDENCE_READINESS_SCORECARD = "readiness_scorecard"
EVIDENCE_STORY_PACK = "cross_workflow_story_pack"
EVIDENCE_PORTFOLIO_PACK = "portfolio_evidence_pack"
EVIDENCE_RELEASE_VERIFIER = "release_verifier"
EVIDENCE_PILOT_READINESS = "pilot_readiness"

# Artifacts required for PASS_CONTROLLED_DEMO_90
REQUIRED_EVIDENCE = (
    EVIDENCE_BOUNDED_VALIDATION,
    EVIDENCE_READINESS_SCORECARD,
    EVIDENCE_STORY_PACK,
    EVIDENCE_PORTFOLIO_PACK,
)

# ---------------------------------------------------------------------------
# Allowed wording (may be used in portfolio / docs if gate PASSES)
# ---------------------------------------------------------------------------

ALLOWED_WORDING = (
    "TaskFrame Runtime has reached 90%+ controlled demo / portfolio readiness, "
    "supported by fresh bounded validation, readiness scorecard, cross-workflow "
    "demo evidence, and portfolio evidence artifacts."
)

# ---------------------------------------------------------------------------
# Disallowed wording — must not appear in any portfolio/docs/UI claim
# unless a separate production-readiness gate explicitly passes
# ---------------------------------------------------------------------------

DISALLOWED_CLAIMS: list[str] = [
    "Production ready",
    "Enterprise production ready",
    "Safe for unsupervised live automation",
    "Live side effects fully enabled",
    "90% production readiness",
    "Autonomous production worker",
]

# ---------------------------------------------------------------------------
# Disclaimer that must accompany any passing-gate claim
# ---------------------------------------------------------------------------

CLAIM_DISCLAIMER = (
    "This evidence supports controlled demo / portfolio readiness only. "
    "It does not establish full production readiness."
)
