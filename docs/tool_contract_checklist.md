# Tool Contract Checklist

## Tool identity

- [ ] Tool has a clear namespace/action.
- [ ] Tool performs one capability.
- [ ] Tool name does not imply broader orchestration than it performs.

## Risk classification

- [ ] Tool is classified as read-only, transform, prepare, side-effect, live side-effect, or optional/high-risk.
- [ ] Side-effect classification is conservative.
- [ ] Optional/RPA status is explicitly stated.

## Implementation

- [ ] Tool function accepts explicit arguments.
- [ ] Tool function does not mutate TaskFrame directly.
- [ ] Tool function does not call orchestrator.
- [ ] Tool function does not select other tools.
- [ ] Tool function returns structured data.

## Registry

- [ ] Tool is registered in `TOOL_REGISTRY`.
- [ ] `required_args` are complete.
- [ ] `optional_args` are complete.
- [ ] `arg_types` are defined where coercion is needed.
- [ ] `output_type` is specific.
- [ ] `side_effect` is correct.
- [ ] `requires_approval` is correct.
- [ ] Live flags are correct.

## Capability status

- [ ] Tool has capability registry metadata.
- [ ] Tool has category.
- [ ] Tool has core or optional flag.
- [ ] Tool has auth requirement.
- [ ] Tool has limitations.
- [ ] Tool appears in operator tool status.

## Health and setup

- [ ] Tool has a safe health check.
- [ ] Health check avoids live side effects.
- [ ] Health check returns structured status.
- [ ] Setup instructions exist.
- [ ] Safe setup does not mutate external systems.

## Manifest use

- [ ] Tool is used only through manifest steps.
- [ ] Manifest command uses explicit output alias.
- [ ] Required prior outputs are validated.
- [ ] Completion contract matches tool behavior.
- [ ] Side-effect tools create `PendingAction` records.

## Live execution

- [ ] Live execution is blocked by default.
- [ ] Live side effect has explicit guardrail if enabled.
- [ ] Manifest allowlist is required for live execution.
- [ ] Approval is required before execution.
- [ ] Tests cover blocked live execution.

## Tests

- [ ] Registry test added.
- [ ] Argument validation test added.
- [ ] Dry-run test added.
- [ ] Side-effect staging test added if relevant.
- [ ] Health check test added.
- [ ] Setup instruction test added.
- [ ] Optional boundary test added if optional.
- [ ] Release verifier impact considered.

## Documentation

- [ ] Tool is documented.
- [ ] Operator setup notes are documented.
- [ ] Known limitations are documented.
- [ ] Default RC inclusion or exclusion is documented.
