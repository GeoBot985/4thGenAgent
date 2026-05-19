# 90% Readiness Scorecard

## Purpose

This scorecard measures controlled portfolio/demo readiness across the repository. It does not certify production deployment readiness.

## Areas Assessed

- Core Architecture
- Manifest Runtime
- Event Routing
- Business Workflows
- Tooling
- Release Verification
- Production Readiness

## Scoring Rules

- PASS check: full points
- WARN check: half points
- FAIL check: zero points
- NOT_ASSESSED: zero points

Area scores are calculated from weighted checks. The overall score is the average of the seven area scores.

## Release Gate Behaviour

The release gate fails if any area scores below the configured threshold. In strict mode, WARN, FAIL, and NOT_ASSESSED areas are blocking.

## How to Run

```bash
python -m src.taskframe_cli readiness --strict
python -m src.taskframe_cli readiness --json
python -m src.taskframe_cli readiness --strict --open-report
```

## How to Interpret Results

- Overall score should be at or above 90 for the controlled release gate.
- Blocking areas indicate which project areas still need work.
- Report paths point to the generated JSON, Markdown, and HTML artifacts under `runtime_data/readiness/`.

## Known Limitations

This scorecard measures controlled demo and portfolio readiness. It does not certify production deployment readiness.
