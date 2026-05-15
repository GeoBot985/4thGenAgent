# Quickstart Guide

## Purpose

This guide walks you through cloning, installing, and running TaskFrame Runtime for the first time. The full path takes under 5 minutes on a clean machine with Python 3.11+.

---

## Requirements

- Python 3.11 or later
- Git
- A terminal (PowerShell on Windows, bash/zsh on Linux/macOS)
- No Google account, Playwright, Ollama, or browser setup required for the default demo
- The quickstart uses the safe default configuration and does not require live credentials or browser profiles

---

## Windows setup

```powershell
git clone <repo-url>
cd <repo-folder>
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

Verify the install:

```powershell
taskframe version
```

---

## Linux / macOS setup

```bash
git clone <repo-url>
cd <repo-folder>
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Verify the install:

```bash
taskframe version
```

---

## Run your first demo

```bash
taskframe demo
```

This runs a safe dry-run business scenario. Expected output includes:

- the scenario name
- the final TaskFrame state
- the frame ID
- the report path (if a report was generated)

No live email, message, or sheet write is performed.

---

## Open the UI

```bash
taskframe ui
```

This opens the Operator Demo Console (Tkinter). The normal demo path is:

```
Select demo → Start demo → Review result → Approve dry-run action → Open report
```

If the UI does not open, see the Troubleshooting section below.

---

## Run verification

```bash
taskframe verify
```

This runs the release verification script. It checks:

- imports
- CLI packaging
- manifest health
- tool registry
- scenario pack
- golden demo
- release artifacts

Results are written to `runtime_data/audit/release_candidate_verification.json` and `docs/release_candidate_verification.md`.

---

## Understand dry-run safety

The default install and demo path are dry-run safe.

By default:

- no live emails are sent;
- no live Google Sheets are written;
- no live calendar events are created;
- no browser/RPA tools are launched;
- no live WhatsApp or Google Messages actions are performed;
- LLM calls use the deterministic fake path unless explicitly configured otherwise.

Side-effecting actions (such as sending a customer message) are staged as **pending actions**. They are shown in the UI and the run report, but they are not executed unless an operator explicitly approves live execution — which is disabled in the default demo path.

---

## Optional integrations

The default demo does not require any of these. Install them only if you need live tool integrations.

### Google tools

```bash
pip install -e ".[google]"
```

Required for: Gmail, Google Sheets, Google Calendar tools.

### RPA tools

```bash
pip install -e ".[rpa]"
playwright install
```

Required for: browser-backed automation (Google Messages, WhatsApp Web). Requires local browser profiles and manual authentication. Excluded from the default demo path.

### Development tools

```bash
pip install -e ".[dev]"
python -m pytest
```

Installs test dependencies and runs the full test suite.

---

## Troubleshooting

| Problem | Suggested fix |
|---|---|
| `taskframe` command not found | Ensure the virtual environment is active and `pip install -e .` completed successfully. |
| Tkinter UI does not open | Use `taskframe demo` (CLI) first. Ensure Python was installed with Tkinter support. On Linux, install `python3-tk` via your package manager. |
| Manifest health reports failures | Run `taskframe manifest-health --strict --no-smoke` to see the exact failures. Check the generated manifest health report. |
| Google dependencies missing | Install `pip install -e ".[google]"` only if you are using Google tools. Not needed for the default demo. |
| Playwright missing | Install `pip install -e ".[rpa]"` and run `playwright install` only if using RPA tools. |
| Ollama unavailable | The default demo uses the deterministic fake LLM path. Ollama is optional and not required for `taskframe demo` or `taskframe verify`. |
| Tests fail on import | Ensure the virtual environment is active and `pip install -e ".[dev]"` completed. |
