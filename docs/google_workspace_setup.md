# Google Workspace Setup

## OAuth credential files

Store Google credentials in your user config directory, typically `~/.taskframe/google/`.
Use placeholder example files as a starting point and keep real secrets out of the repo.

## Optional dependency install

The pack uses Google client libraries only when you install the Google extra.

```bash
pip install -e ".[google]"
```

## Validate the pack

```bash
python -m src.taskframe_cli tools validate tool_packs/google_workspace/toolpack.json
python -m src.taskframe_cli tools health google_workspace
```

## Safe health checks

Use the default local health path first:

```bash
python -m src.taskframe_cli tools health google_workspace
```

## Optional live-read integration tests

Set the integration flag and provide credentials before running the live-read tests.

## What the pack cannot do

- send Gmail;
- create, update, or delete Calendar events;
- write Sheets data;
- access Drive write operations;
- expose OAuth token contents.
