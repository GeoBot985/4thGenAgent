# Runtime Tool Governance

Runtime governance is the execution-time policy layer that sits between tool discovery and tool invocation.

Discovery tells the operator that a tool exists.
Governance decides whether that tool may execute in the current runtime environment.

## Runtime environment model

Supported environments:

- `demo`
- `dev`
- `test`
- `release`
- `live`

Resolution order:

1. explicit runtime engine / tool runner argument
2. `TASKFRAME_ENV`
3. `config/runtime_profile.json`
4. fallback to `demo`

## Decision model

The runtime evaluates each tool call and returns one of:

- `ALLOW`
- `WARN`
- `BLOCK`

Blocked calls fail safely with a canonical `ToolResult` and a TaskFrame audit event.

## What is checked

Governance is checked before:

- normal tool execution
- pending action staging
- pending action execution
- live health probes
- external toolpack execution

## Core rules

- Built-in core tools are allowed in `demo` unless another safety gate fails.
- Optional packs must be explicitly enabled for the environment.
- Blocked packs stay blocked in every environment.
- High-risk and experimental packs are blocked in safe-release environments.
- Live side effects require both approval and a runtime policy that allows them.

## Pending actions

Pending actions carry governance metadata so the runtime can re-check policy before execution.

If policy changes after staging, execution fails safely instead of silently proceeding.

## Health probes

Health probes are not exempt from governance.

Live probes are only allowed when the pack is enabled and the runtime policy permits them.

Optional RPA probes remain excluded from the default release-candidate path.

## Troubleshooting blocked tools

When a tool is blocked:

1. check the runtime environment
2. check the pack governance policy
3. check whether the pack is enabled for that environment
4. check whether the call requests live side effects
5. inspect the TaskFrame audit record

Discovery is not execution permission. A discovered tool can still be blocked by runtime governance.
