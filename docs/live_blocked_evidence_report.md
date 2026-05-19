# Live-Blocked Evidence Report

## Verdict

**PASS**

Generated: 2026-05-19T18:39:28.815335Z

## What Was Tested

- Runtime live mode disabled
- Manifest live policy disabled
- Tool live side-effect policy disabled
- Pending action not approved
- Wrong confirmation phrase
- Optional RPA default exclusion

## Evidence Table

| Check | Expected | Actual | Status |
|---|---|---|---|
| runtime_live_disabled | disabled | disabled | PASS |
| manifest_live_disabled | 0 manifests with live_execution.enabled=true | 0 manifests with live_execution.enabled=true | PASS |
| tool_live_blocked | all side-effect tools require approval or have live blocked | all tools compliant | PASS |
| pending_action_not_approved | PENDING_APPROVAL state requires explicit approval before execution | State machine: PENDING_APPROVAL → APPROVED → EXECUTING → EXECUTED | PASS |
| wrong_confirmation_blocked | typed confirmation required for live execution | EXECUTE LIVE <frame_id> <action_id> format required | PASS |
| optional_rpa_excluded | rpa_google_messages excluded_from_default_release=True | excluded | PASS |

## Live Attempt Results

No live side effects were performed.

No live side effects were performed.