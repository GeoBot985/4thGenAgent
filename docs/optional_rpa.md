# Optional RPA Tools

## Overview

TaskFrame Runtime includes optional browser-backed RPA tooling, specifically for Google Messages automation experiments.

These tools are **excluded from the default demo and release path**. They exist to demonstrate future automation reach, not as a default capability.

---

## Why RPA is optional

Browser-backed automation depends on:

- a local Playwright installation;
- a local browser profile;
- an authenticated and manually paired browser session;
- local machine state that changes between sessions.

These dependencies cannot be installed or configured automatically and are not safe to assume in a shared or unfamiliar environment.

---

## Safety warning

Optional RPA tools may interact with local browser sessions and authenticated web applications.

They are excluded from the default demo and release path.

**Do not enable RPA tools against sensitive accounts unless you understand the browser profile, authentication, and data exposure risks.**

If a browser session is configured with access to personal or business accounts, an RPA probe may read or interact with that account's messages.

---

## What is excluded from the default path

The following are **not** required for or included in the default demo:

- `pip install playwright` — not in default dependencies
- browser profile setup — not part of default installation
- `taskframe demo` — does not use RPA tools
- `taskframe ui` — shows RPA capability status as `disabled_optional`, does not run live probes
- `taskframe verify` — does not run RPA live probes
- `python -m pytest` — default tests do not require Playwright
- `taskframe golden-demo` — does not include RPA scenarios

---

## Dependencies

To install optional RPA dependencies:

```bash
pip install -e ".[rpa]"
playwright install
```

This installs Playwright and its browser binaries. It is **not** part of the default install.

---

## Configuration

RPA configuration must remain **user-local**. Do not commit browser profiles, session files, or tokens to the repository.

Recommended config location: `~/.taskframe/`

The recommended profile for RPA work is `rpa-local`. See `docs/configuration.md` for details.

Environment variable to enable optional RPA:

```bash
ENABLE_OPTIONAL_RPA_TOOLS=true
```

Or set the profile explicitly:

```bash
TASKFRAME_PROFILE=rpa-local
```

---

## Browser profile risks

- Browser profiles may include authenticated sessions for personal accounts.
- An RPA live probe may read or send messages if the browser is paired.
- Do not use browser profiles that contain sensitive business or personal communications unless you are operating in a controlled local environment.
- Never share browser profile directories or include them in the repository.

---

## Live probe behaviour

A live probe explicitly runs the RPA tool against a local browser session.

To run a live probe via CLI:

```bash
taskframe rpa health --enable-rpa --live-probe
```

`--live-probe` requires `--enable-rpa`. Running `--live-probe` without `--enable-rpa` will fail with a clear error.

Live probes are **never** run automatically during:

- `taskframe demo`
- `taskframe verify`
- `python -m pytest`
- `taskframe golden-demo`

---

## Troubleshooting

| Problem | Suggested fix |
|---|---|
| `playwright not found` | Run `pip install -e ".[rpa]" && playwright install` |
| `rpa health` shows `disabled` | Set `ENABLE_OPTIONAL_RPA_TOOLS=true` or use `--enable-rpa` flag |
| Browser not paired | Manually pair Google Messages in the Playwright browser (`playwright open`) |
| Live probe fails auth | Re-authenticate the browser session manually |
| `taskframe rpa health --live-probe` fails | Add `--enable-rpa` flag: `taskframe rpa health --enable-rpa --live-probe` |

---

## Recommended use

Optional RPA tools are recommended only for:

- local developer experiments in a controlled environment;
- demonstrating future automation reach in a prepared lab setup;
- validating a specific RPA workflow that has been explicitly designed and approved.

They are **not** recommended for:

- default portfolio demonstrations;
- production or staging environments;
- machines shared with other users;
- accounts with access to sensitive business messages.

---

## CLI reference

```bash
taskframe rpa status              # Show optional RPA status (no probe)
taskframe rpa health              # Default: show RPA health as disabled
taskframe rpa health --enable-rpa # Run dependency and config checks
taskframe rpa health --enable-rpa --live-probe  # Run live browser probe
taskframe rpa docs                # Print this documentation path
```

See `docs/cli_reference.md` for full CLI documentation.
