# Tool Pack Examples

## Safe demo pack

The repository includes `tool_packs/demo_echo/` as a safe example.

It provides:

- `echo/echo`
- `echo/summarize_args`
- `echo/fail`

## Example manifest step

```text
[t:echo/echo -> echoed] message="Hello"
```

## Example discovery output

```text
taskframe tools discover
Tool pack discovery:
Enabled count: 1
Registered tool count: 0
```

## Example validation output

```text
taskframe tools validate tool_packs/demo_echo/toolpack.json
Status: PASS
```


## Google Workspace examples

The Google Workspace tool pack includes example manifests for Gmail unread checks, Calendar search, and Sheets range reads under `tool_packs/google_workspace/examples/`.

These examples are read-only and are intended for explicit validation or integration testing only.
