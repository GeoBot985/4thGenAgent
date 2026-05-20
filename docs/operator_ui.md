# Operator UI

The operator UI is a control surface for demo, inspect, and controlled pilot workflows. It shows runtime state, approval flows, evidence, tool health, and operational health without inventing its own execution model.

## Operational Health Panel

The **Operational Health** section surfaces the monitoring index built from runtime artifacts.

It shows:

- run health summary
- failed runs
- pending approvals
- stuck runs
- tool health
- external dependency issues
- runtime store status
- recommended operator actions

The panel reuses runtime-store and tool-health data. It does not trigger live side effects, automatic retries, or destructive cleanup.

## Safety Boundary

The operator UI remains a controlled demo and pilot workspace.

- It does not claim full production monitoring.
- It does not enable live writes, sends, deletes, or automatic recovery.
- It is intended to help an operator inspect failure visibility and readiness before any future production automation work.
