# Readiness Evidence Gate

**Spec 147** — Fresh Readiness Evidence Gate + 90% Claim Enforcement

---

## Purpose

The Readiness Evidence Gate determines whether the project may currently claim:

> **90%+ controlled demo / portfolio readiness**

The gate evaluates freshly generated evidence artifacts, applies deterministic
rules, and produces a structured PASS/FAIL verdict. It never runs tests directly.

---

## What This Gate Does NOT Claim

The gate explicitly states:

> This evidence supports **controlled demo / portfolio readiness only**. It does
> not establish full production readiness.

The following claims are **disallowed** unless a separate production-readiness
gate explicitly passes:

- Production ready
- Enterprise production ready
- Safe for unsupervised live automation
- Live side effects fully enabled
- 90% production readiness
- Autonomous production worker

---

## CLI Usage

```bash
# Basic check
taskframe readiness-gate --threshold 90

# With freshness enforcement
taskframe readiness-gate --threshold 90 --since "2026-05-22T00:00:00Z"

# Write all three report formats (JSON, Markdown, HTML)
taskframe readiness-gate --threshold 90 --write-report

# Strict mode (release verifier evidence is required, not just a warning)
taskframe readiness-gate --threshold 90 --strict

# Machine-readable JSON output
taskframe readiness-gate --threshold 90 --json
```

---

## Required Evidence

The gate inspects four required artifacts and two optional ones:

| Artifact | Required | Default Location |
|---|---|---|
| Bounded validation report | **Yes** | `runtime_data/validation/bounded_validation_report.json` |
| Readiness scorecard | **Yes** | `runtime_data/readiness/readiness_scorecard.json` |
| Cross-workflow story/demo pack | **Yes** | `runtime_data/demo_packs/<latest>/cross_workflow_demo_summary.json` |
| Portfolio evidence pack | **Yes** | `runtime_data/portfolio_evidence/<latest>/summary.json` |
| Release verifier evidence | Warning / Strict | `runtime_data/audit/release_candidate_verification.json` |
| Pilot readiness | Optional | `runtime_data/pilot_readiness/<latest>/pilot_readiness_scorecard.json` |

---

## Gate Rules

The gate PASSES only when **all** of the following are true:

1. **Bounded validation report** — exists, `ok == true`
2. **Readiness scorecard** — exists, `ok == true`, `overall_score >= threshold`, `status == "PASS"`
3. **Portfolio evidence pack** — exists, `ok == true`, `production_readiness_claimed == false`,
   `included_readiness_scorecard == true`, `included_story_pack == true`
4. **Cross-workflow story pack** — exists, `ok == true`, `dry_run_only == true`,
   `live_side_effects_performed != true`
5. **No evidence file** claims full production readiness
6. **No required artifact** is stale (if `--since` is provided or git HEAD is available)

---

## Freshness Enforcement

By default, the gate attempts to read the **git HEAD commit timestamp** and
requires all evidence to be newer than that timestamp.

Override with `--since`:

```bash
taskframe readiness-gate --since "2026-05-22T00:00:00Z"
```

Each artifact's freshness status is reported as:

| Status | Meaning |
|---|---|
| `PASS` | Artifact exists, valid, and fresh |
| `FAIL` | Artifact exists but fails gate rules |
| `STALE` | Artifact exists but is older than the `--since` timestamp |
| `MISSING` | Artifact file not found |

---

## Output Shape

```json
{
  "ok": true,
  "claim": "90%+ controlled demo / portfolio readiness",
  "claim_allowed": true,
  "threshold": 90,
  "overall_score": 100.0,
  "status": "PASS",
  "classification": "PASS_CONTROLLED_DEMO_90",
  "production_readiness_claimed": false,
  "production_claim_status": "PRODUCTION_NOT_CLAIMED",
  "controlled_demo_readiness_claimed": true,
  "evidence": {
    "bounded_validation": { "status": "PASS", "fresh": true, "path": "..." },
    "readiness_scorecard": { "status": "PASS", "fresh": true, "score": 100.0, "path": "..." },
    "cross_workflow_story_pack": { "status": "PASS", "fresh": true, "path": "..." },
    "portfolio_evidence_pack": { "status": "PASS", "fresh": true, "path": "..." },
    "release_verifier": { "status": "PASS", "fresh": true, "verdict": "READY_WITH_KNOWN_LIMITATIONS", "path": "..." }
  },
  "blocking_failures": [],
  "warnings": [],
  "recommended_next_steps": [],
  "generated_at": "2026-05-22T...",
  "disclaimer": "This evidence supports controlled demo / portfolio readiness only. It does not establish full production readiness.",
  "allowed_wording": "TaskFrame Runtime has reached 90%+ controlled demo / portfolio readiness...",
  "disallowed_claims": ["Production ready", "Enterprise production ready", ...]
}
```

---

## Claim Classification Codes

| Code | Meaning |
|---|---|
| `PASS_CONTROLLED_DEMO_90` | Gate passes at 90% controlled-demo threshold |
| `FAIL_CONTROLLED_DEMO_90` | Gate fails at 90% controlled-demo threshold |
| `PASS_PILOT_READINESS` | (Future) Pilot readiness gate passes |
| `FAIL_PILOT_READINESS` | (Future) Pilot readiness gate fails |
| `PRODUCTION_NOT_CLAIMED` | No production readiness claim is being made |
| `PRODUCTION_CLAIM_BLOCKED` | A production readiness claim was detected and blocked |

---

## Report Output

When `--write-report` is used, three files are written to
`runtime_data/readiness_gate/`:

| File | Purpose |
|---|---|
| `readiness_gate_report.json` | Full machine-readable result |
| `readiness_gate_report.md` | Human-readable summary with evidence table |
| `readiness_gate_report.html` | Browser-viewable HTML version |

The Markdown report includes:
- Claim being evaluated and threshold
- Final verdict and classification code
- Evidence status table
- Freshness table
- Blocking failures (if any)
- Warnings
- Recommended next steps
- Allowed portfolio/docs wording (if PASS)
- Disallowed wording list

---

## Generating Fresh Evidence

To get a fresh PASS, regenerate all required evidence in order:

```bash
# 1. Run bounded validation
python tools/run_bounded_validation.py local

# 2. Build readiness scorecard
taskframe readiness --threshold 90

# 3. Run cross-workflow demo pack
taskframe demo cross-workflow-v2

# 4. Build portfolio evidence pack
taskframe portfolio-pack

# 5. Evaluate the gate
taskframe readiness-gate --threshold 90 --write-report
```

---

## Operator UI Panel

A status card may be displayed in the Operator UI showing:

```
90% Readiness Gate
Status:           PASS / FAIL / STALE / MISSING
Claim Allowed:    Yes / No
Latest Report:    [open link]
Blocking Failures: 0
```

The UI must not display a 90% readiness claim unless the gate result is PASS.

---

## Files

| File | Description |
|---|---|
| `src/readiness_evidence_gate.py` | Core gate logic |
| `runtime/readiness_evidence_contracts.py` | Shared constants and claim labels |
| `tests/test_readiness_evidence_gate.py` | Test suite (37 tests) |
| `docs/readiness_evidence_gate.md` | This document |
