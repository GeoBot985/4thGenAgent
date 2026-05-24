# InvoiceOps Showcase Live Runbook

## Prerequisites

1. Google service account credentials configured for Sheets API.
2. A Google Spreadsheet created and shared with the service account.
3. `controlled_live_write` profile configured in your TaskFrame config.
4. Showcase config at `~/.taskframe/invoiceops_showcase.json` with `spreadsheet_id` set.

## Quick Boundary-Only Run (No Google Credentials Required)

Verify the showcase works end-to-end in boundary mode (no live writes):

```bash
python -m src.taskframe_cli invoiceops showcase status --json

python -m src.taskframe_cli invoiceops showcase run \
  --profile controlled_live_write \
  --invoice-limit 1 \
  --json
```

Expected: `"live_side_effects_performed": false`, `"live_writes_performed": 0`.

## Full Live Demo Run

### Step 1 — Check showcase status

```bash
python -m src.taskframe_cli invoiceops showcase status \
  --spreadsheet-id "<spreadsheet_id>" \
  --json
```

Verify `"status": "ready"` and `"invoice_fixture_count": 8`.

### Step 2 — Set up the demo sheet

Seeds supplier master, PO register, and goods receipt data:

```bash
python -m src.taskframe_cli invoiceops showcase setup-sheet \
  --profile controlled_live_write \
  --spreadsheet-id "<spreadsheet_id>" \
  --confirm "EXECUTE LIVE INVOICEOPS SHOWCASE <spreadsheet_id>" \
  --json
```

### Step 3 — Run the showcase

```bash
python -m src.taskframe_cli invoiceops showcase run \
  --profile controlled_live_write \
  --spreadsheet-id "<spreadsheet_id>" \
  --reset-sheet \
  --write-report \
  --confirm "EXECUTE LIVE INVOICEOPS SHOWCASE <spreadsheet_id>" \
  --live \
  --json
```

### Step 4 — Open the report

```bash
python -m src.taskframe_cli invoiceops showcase open-report
```

## Confirmation Phrase

The required typed confirmation phrase is:

```
EXECUTE LIVE INVOICEOPS SHOWCASE <spreadsheet_id>
```

No confirmation, no live writes. There is no override.

## Environment Variable (Live Integration Tests)

```powershell
$env:RUN_LIVE_INVOICEOPS_SHOWCASE = "1"
python -m pytest tests/integration/test_invoiceops_showcase_live_google_sheet.py -q
```

## Rollback / Reset

The showcase does not perform automatic rollback. If you need to undo live writes:

1. Open the **Rollback Plans** tab in the Google Sheet.
2. For each row, use the idempotency key to locate and delete the corresponding row from the target register.
3. Rollback is always manual. No automated compensation is provided.

To reset the entire demo sheet, re-run the showcase with `--reset-sheet`. This clears all data tabs and re-seeds master data.

## Safety Rules

| Rule | Enforcement |
|------|-------------|
| Only `controlled_live_write` profile | Blocked at CLI level |
| Only configured showcase spreadsheet | Blocked by confirmation phrase mismatch |
| Typed confirmation required | Required argument; no default |
| Idempotency key per write | Generated from `sha256(showcase:{run_id}:{invoice}:{target})` |
| Payload hash per write | Generated from `sha256(json.dumps(payload, sort_keys=True))` |
| RPA blocked | Governed by profile |
| Gmail send blocked | Governed by profile |
| Calendar mutation blocked | Governed by profile |

## Troubleshooting

**"status: needs_config"** → Add `spreadsheet_id` to `~/.taskframe/invoiceops_showcase.json`.

**"confirmation_required" blocker** → The `--confirm` value must exactly match `EXECUTE LIVE INVOICEOPS SHOWCASE <spreadsheet_id>`. No trailing spaces or quotes.

**"profile_required" blocker** → Pass `--profile controlled_live_write`.

**Live writes = 0 in live mode** → Check that `--live` flag was passed and blockers list is empty.
