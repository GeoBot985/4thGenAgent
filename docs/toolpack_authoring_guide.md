# Tool Pack Authoring Guide

## 1. Start with a safe pack

Use a harmless pack first. The demo echo pack exists to prove the contract without introducing external dependencies or live side effects.

## 2. Keep the pack self-contained

Put pack code, health checks, and README content inside one folder. Do not import browser or cloud dependencies from default runtime imports.

## 3. Declare tool safety explicitly

Side-effect tools must declare:

- `side_effect: true`
- `requires_approval: true`
- `allow_live: true` only when intended
- `allow_live_side_effect: true` only when explicitly permitted and tested

## 4. Validate before registering

Use:

```bash
taskframe tools validate tool_packs/demo_echo/toolpack.json
```

## 5. Inspect health

Use:

```bash
taskframe tools health demo_echo
```

## 6. Enable packs through config

Add enabled pack paths to `config/enabled_toolpacks.json`.

Optional packs remain excluded until explicit enablement is provided in configuration.

## 7. Keep manifests registry-driven

Manifests should reference tool keys only. They should never import pack modules directly.
