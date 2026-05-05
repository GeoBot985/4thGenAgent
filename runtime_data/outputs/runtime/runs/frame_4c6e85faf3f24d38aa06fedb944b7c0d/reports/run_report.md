# TaskFrame Run Report

## 1. Executive Summary

| Field | Value |
|---|---|
| Frame ID | frame_4c6e85faf3f24d38aa06fedb944b7c0d |
| Manifest | procurement.low_stock_reorder |
| State | WAITING_FOR_EXECUTE |
| Outcome | Run completed to approval gate. Side effect is staged but not executed. |
| Pending Actions | 1 |
| Executed Actions | 0 |
| Errors | 0 |

## 2. Trigger / Event

- Event ID: evt_0c5a9aada45d43a0950626cb028b09da
- Event Type: manual.procurement_low_stock_reorder
- Source: operator_scenario_pack

```json
{
  "event_id": "evt_0c5a9aada45d43a0950626cb028b09da",
  "event_type": "manual.procurement_low_stock_reorder",
  "source": "operator_scenario_pack"
}
```

## 3. Route and Manifest

- Manifest ID: procurement.low_stock_reorder
- Manifest Name: 
- Step Count: 8
- Validation Count: 8

## 4. Runtime Final State

- Final State: WAITING_FOR_EXECUTE
- Current Step ID: 
- Errors Count: 0

```json
{
  "errors": [],
  "failed_steps": [],
  "final_state": "WAITING_FOR_EXECUTE",
  "message": "Required pending action exists. Waiting for approval.",
  "missing_executed_actions": [],
  "missing_outputs": [],
  "missing_pending_actions": [],
  "ok": true,
  "status": "AWAITING_APPROVAL",
  "validation_summary": {
    "failed": 0,
    "passed": 8
  }
}
```

## 5. Step Timeline

| # | Step | Kind | Action | Status | Attempts | Result | Error |
|---:|---|---|---|---|---:|---|---|
| 1 | search_low_stock_inventory | tool | search_low_stock | COMPLETED | 1 | low_stock_items |  |
| 2 | filter_reorder_candidates | tool | filter_reorder_candidates | COMPLETED | 1 | reorder_candidates |  |
| 3 | check_duplicate_open_pos | tool | check_duplicate_open | COMPLETED | 1 | duplicate_po_check |  |
| 4 | select_supplier | tool | select_for_sku | COMPLETED | 1 | selected_supplier |  |
| 5 | build_draft_po | tool | build_draft | COMPLETED | 1 | draft_po |  |
| 6 | validate_draft_po | tool | validate_draft | COMPLETED | 1 | po_validation |  |
| 7 | draft_supplier_message | llm | draft_supplier_reorder_message | COMPLETED | 1 | supplier_message |  |
| 8 | prepare_supplier_send | tool | prepare_message_action | STAGED | 1 | supplier_message_send |  |

## 6. LLM Calls

- step_id: draft_supplier_message
  action: draft_supplier_reorder_message
  provider: fake
  model: fake
  ok: True
  output_ref: 
  micro_tool: True
## 7. Tool Calls

- step_id: search_low_stock_inventory
  tool: inventory/search_low_stock
  namespace: inventory
  action: search_low_stock
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: low_stock_items
  ok: True
  error: 
- step_id: filter_reorder_candidates
  tool: inventory/filter_reorder_candidates
  namespace: inventory
  action: filter_reorder_candidates
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: reorder_candidates
  ok: True
  error: 
- step_id: check_duplicate_open_pos
  tool: po/check_duplicate_open
  namespace: po
  action: check_duplicate_open
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: duplicate_po_check
  ok: True
  error: 
- step_id: select_supplier
  tool: supplier/select_for_sku
  namespace: supplier
  action: select_for_sku
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: selected_supplier
  ok: True
  error: 
- step_id: build_draft_po
  tool: po/build_draft
  namespace: po
  action: build_draft
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: draft_po
  ok: True
  error: 
- step_id: validate_draft_po
  tool: po/validate_draft
  namespace: po
  action: validate_draft
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: po_validation
  ok: True
  error: 
- step_id: prepare_supplier_send
  tool: supplier/prepare_message_action
  namespace: supplier
  action: prepare_message_action
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: supplier_message_send
  ok: True
  error: 
## 8. Outputs

### Output: draft_po
```json
{
  "currency": "ZAR",
  "lines": [
    {
      "line_total": 4410.0,
      "name": "Keyboard",
      "quantity": 21,
      "sku": "SKU-1002",
      "unit_cost": 210.0
    }
  ],
  "po_id": "PO-DRAFT-20260504-202835-C831E7",
  "status": "draft",
  "supplier_id": "SUP-1001",
  "supplier_name": "Cape Tech Supplies",
  "total": 4410.0
}
```

### Output: duplicate_po_check
```json
{
  "blocked_count": 1,
  "duplicates": [
    {
      "po_id": "PO-9001",
      "sku": "SKU-1001",
      "status": "open"
    }
  ],
  "valid_candidates": [
    {
      "available_stock": 9,
      "currency": "ZAR",
      "name": "Keyboard",
      "preferred_supplier_id": "SUP-1001",
      "reorder_qty": 21,
      "reorder_threshold": 10,
      "sku": "SKU-1002",
      "target_stock_level": 30,
      "unit_cost": 210.0
    }
  ],
  "valid_count": 1
}
```

### Output: low_stock_items
```json
{
  "count": 6,
  "items": [
    {
      "available_stock": 2,
      "name": "LED desk lamp",
      "reorder_quantity": 20,
      "reorder_threshold": 5,
      "reserved_stock": 1,
      "sku": "SKU-LAMP-01",
      "status": "active",
      "stock_on_hand": 3,
      "supplier_id": "SUP-002"
    },
    {
      "available_stock": 0,
      "name": "Ergonomic office chair",
      "reorder_quantity": 8,
      "reorder_threshold": 3,
      "reserved_stock": 0,
      "sku": "SKU-CHAIR-01",
      "status": "active",
      "stock_on_hand": 0,
      "supplier_id": "SUP-001"
    },
    {
      "available_stock": 2,
      "name": "Compact printer",
      "reorder_quantity": 5,
      "reorder_threshold": 3,
      "reserved_stock": 0,
      "sku": "SKU-PRINTER-01",
      "status": "active",
      "stock_on_hand": 2,
      "supplier_id": "SUP-002"
    },
    {
      "available_stock": 4,
      "name": "Monitor stand",
      "reorder_quantity": 10,
      "reorder_threshold": 4,
      "reserved_stock": 2,
      "sku": "SKU-STAND-01",
      "status": "active",
      "stock_on_hand": 6,
      "supplier_id": "SUP-001"
    },
    {
      "available_stock": 4,
      "currency": "ZAR",
      "name": "Wireless Mouse",
      "preferred_supplier_id": "SUP-1001",
      "reorder_threshold": 10,
      "sku": "SKU-1001",
      "target_stock_level": 40,
      "unit_cost": 125.5
    },
    {
      "available_stock": 9,
      "currency": "ZAR",
      "name": "Keyboard",
      "preferred_supplier_id": "SUP-1001",
      "reorder_threshold": 10,
      "sku": "SKU-1002",
      "target_stock_level": 30,
      "unit_cost": 210.0
    }
  ]
}
```

### Output: po_validation
```json
{
  "checks": [
    {
      "id": "po_has_id",
      "message": "Draft PO has a po_id.",
      "ok": true
    },
    {
      "id": "po_has_supplier_id",
      "message": "Draft PO has a supplier_id.",
      "ok": true
    },
    {
      "id": "po_status_draft",
      "message": "Draft PO status is draft.",
      "ok": true
    },
    {
      "id": "po_has_lines",
      "message": "Draft PO has at least one line.",
      "ok": true
    },
    {
      "id": "po_line_sku",
      "message": "Each line has a sku.",
      "ok": true
    },
    {
      "id": "po_line_qty_positive",
      "message": "Each line quantity is greater than zero.",
      "ok": true
    },
    {
      "id": "po_line_unit_cost_non_negative",
      "message": "Each line unit_cost is non-negative.",
      "ok": true
    },
    {
      "id": "po_line_total_matches",
      "message": "Each line_total matches quantity * unit_cost.",
      "ok": true
    },
    {
      "id": "po_total_matches",
      "message": "PO total matches sum of line totals.",
      "ok": true
    },
    {
      "id": "po_single_currency",
      "message": "Draft PO uses a single currency.",
      "ok": true
    }
  ],
  "errors": [],
  "ok": true
}
```

### Output: reorder_candidates
```json
{
  "candidates": [
    {
      "available_stock": 4,
      "currency": "ZAR",
      "name": "Wireless Mouse",
      "preferred_supplier_id": "SUP-1001",
      "reorder_qty": 36,
      "reorder_threshold": 10,
      "sku": "SKU-1001",
      "target_stock_level": 40,
      "unit_cost": 125.5
    },
    {
      "available_stock": 9,
      "currency": "ZAR",
      "name": "Keyboard",
      "preferred_supplier_id": "SUP-1001",
      "reorder_qty": 21,
      "reorder_threshold": 10,
      "sku": "SKU-1002",
      "target_stock_level": 30,
      "unit_cost": 210.0
    }
  ],
  "count": 2,
  "excluded": [
    {
      "available_stock": 2,
      "name": "LED desk lamp",
      "reorder_quantity": 20,
      "reorder_threshold": 5,
      "reserved_stock": 1,
      "sku": "SKU-LAMP-01",
      "status": "active",
      "stock_on_hand": 3,
      "supplier_id": "SUP-002"
    },
    {
      "available_stock": 0,
      "name": "Ergonomic office chair",
      "reorder_quantity": 8,
      "reorder_threshold": 3,
      "reserved_stock": 0,
      "sku": "SKU-CHAIR-01",
      "status": "active",
      "stock_on_hand": 0,
      "supplier_id": "SUP-001"
    },
    {
      "available_stock": 2,
      "name": "Compact printer",
      "reorder_quantity": 5,
      "reorder_threshold": 3,
      "reserved_stock": 0,
      "sku": "SKU-PRINTER-01",
      "status": "active",
      "stock_on_hand": 2,
      "supplier_id": "SUP-002"
    },
    {
      "available_stock": 4,
      "name": "Monitor stand",
      "reorder_quantity": 10,
      "reorder_threshold": 4,
      "reserved_stock": 2,
      "sku": "SKU-STAND-01",
      "status": "active",
      "stock_on_hand": 6,
      "supplier_id": "SUP-001"
    }
  ]
}
```

### Output: selected_supplier
```json
{
  "excluded_candidates": [],
  "selected_candidates": [
    {
      "available_stock": 9,
      "currency": "ZAR",
      "name": "Keyboard",
      "preferred_supplier_id": "SUP-1001",
      "reorder_qty": 21,
      "reorder_threshold": 10,
      "sku": "SKU-1002",
      "target_stock_level": 30,
      "unit_cost": 210.0
    }
  ],
  "selection_reason": "Preferred active supplier selected for first valid supplier group.",
  "supplier": {
    "email": "orders@capetech.example",
    "lead_time_days": 5,
    "name": "Cape Tech Supplies",
    "supplier_id": "SUP-1001"
  }
}
```

### Output: supplier_message
```json
{
  "body": "Good day Cape Tech Supplies, please find draft purchase order PO-DRAFT-20260504-202835-C831E7 for SKU-1002. Please confirm availability and lead time.",
  "included_po_id": true,
  "included_sku_lines": true,
  "included_supplier_name": true,
  "invented_terms": false,
  "subject": "Purchase Order PO-DRAFT-20260504-202835-C831E7",
  "tone": "professional"
}
```

### Output: supplier_message_send
```json
{
  "action": "prepare_message_action",
  "action_id": "pa_4196ff71304e4d82b8793b913f5a44e4",
  "action_type": "send_supplier_message",
  "args": {
    "body": "Good day Cape Tech Supplies, please find draft purchase order PO-DRAFT-20260504-202835-C831E7 for SKU-1002. Please confirm availability and lead time.",
    "draft_po": {
      "currency": "ZAR",
      "lines": [
        {
          "line_total": 4410.0,
          "name": "Keyboard",
          "quantity": 21,
          "sku": "SKU-1002",
          "unit_cost": 210.0
        }
      ],
      "po_id": "PO-DRAFT-20260504-202835-C831E7",
      "status": "draft",
      "supplier_id": "SUP-1001",
      "supplier_name": "Cape Tech Supplies",
      "total": 4410.0
    },
    "message": {
      "body": "Good day Cape Tech Supplies, please find draft purchase order PO-DRAFT-20260504-202835-C831E7 for SKU-1002. Please confirm availability and lead time.",
      "included_po_id": true,
      "included_sku_lines": true,
      "included_supplier_name": true,
      "invented_terms": false,
      "subject": "Purchase Order PO-DRAFT-20260504-202835-C831E7",
      "tone": "professional"
    },
    "subject": "Purchase Order PO-DRAFT-20260504-202835-C831E7",
    "supplier": {
      "email": "orders@capetech.example",
      "lead_time_days": 5,
      "name": "Cape Tech Supplies",
      "supplier_id": "SUP-1001"
    },
    "to": "orders@capetech.example"
  },
  "body": "Good day Cape Tech Supplies, please find draft purchase order PO-DRAFT-20260504-202835-C831E7 for SKU-1002. Please confirm availability and lead time.",
  "created_at": "2026-05-04T20:28:35Z",
  "namespace": "supplier",
  "output_alias": "supplier_message_send",
  "requires_approval": true,
  "side_effect": true,
  "status": "PENDING_APPROVAL",
  "step_id": "prepare_supplier_send",
  "tool": "supplier/send_message"
}
```

## 9. Evidence

No evidence records were attached to this TaskFrame.
## 10. Validations

| Validation ID | Type | OK | Message | Step | Data |
|---|---|---|---|---|---|
| draft_supplier_reorder_message_subject | llm_micro_tool_schema | ok |  |  | {"subject": "Purchase Order PO-DRAFT-20260504-202835-C831E7"} |
| draft_supplier_reorder_message_body | llm_micro_tool_schema | ok |  |  | {"body": "Good day Cape Tech Supplies, please find draft purchase order PO-DRAFT-20260504-202835-C831E7 for SKU-1002. Please confirm availability and lead time."} |
| draft_supplier_reorder_message_tone | llm_micro_tool_schema | ok |  |  | {"tone": "professional"} |
| draft_supplier_reorder_message_included_po_id | llm_micro_tool_schema | ok |  |  | {"included_po_id": true} |
| draft_supplier_reorder_message_included_supplier_name | llm_micro_tool_schema | ok |  |  | {"included_supplier_name": true} |
| draft_supplier_reorder_message_included_sku_lines | llm_micro_tool_schema | ok |  |  | {"included_sku_lines": true} |
| draft_supplier_reorder_message_invented_terms | llm_micro_tool_schema | ok |  |  | {"invented_terms": false} |
| draft_supplier_reorder_message_tone_allowed | llm_micro_tool_schema | ok |  |  | {"tone": "professional"} |

Passed validations: 8
Failed validations: 0
## 11. Approval / Side-Effect Status

Pending Action Count: 1
Executed Action Count: 0
### Pending Action: pa_4196ff71304e4d82b8793b913f5a44e4
| Field | Value |
|---|---|
| Tool | supplier/send_message |
| Status | PENDING_APPROVAL |
| Risk | side_effect_unknown |
| Requires Approval | True |
| Output Alias | supplier_message_send |
Human Summary: This action would execute tool "supplier/send_message" with the listed arguments.
Arguments: {"body": "Good day Cape Tech Supplies, please find draft purchase order PO-DRAFT-20260504-202835-C831E7 for SKU-1002. Please confirm availability and lead time.", "draft_po": {"currency": "ZAR", "lines": [{"line_total": 4410.0, "name": "Keyboard", "quantity": 21, "sku": "SKU-1002", "unit_cost": 210.0}], "po_id": "PO-DRAFT-20260504-202835-C831E7", "status": "draft", "supplier_id": "SUP-1001", "supplier_name": "Cape Tech Supplies", "total": 4410.0}, "message": {"body": "Good day Cape Tech Supplies, please find draft purchase order PO-DRAFT-20260504-202835-C831E7 for SKU-1002. Please confirm availability and lead time.", "included_po_id": true, "included_sku_lines": true, "included_supplier_name": true, "invented_terms": false, "subject": "Purchase Order PO-DRAFT-20260504-202835-C831E7", "tone": "professional"}, "subject": "Purchase Order PO-DRAFT-20260504-202835-C831E7", "supplier": {"email": "orders@capetech.example", "lead_time_days": 5, "name": "Cape Tech Supplies", "supplier_id": "SUP-1001"}, "to": "orders@capetech.example"}
Guardrails: ["Requires explicit approval before execution.", "UI live execution is disabled in this spec.", "Dry-run mode only."]

## 12. Failure Summary

No failure for this run.
## 13. Artifact Index

| Artifact | Path |
|---|---|
| TaskFrame JSON | runtime_data\outputs\runtime\runs\frame_4c6e85faf3f24d38aa06fedb944b7c0d\taskframe.json |
| Summary JSON | runtime_data\outputs\runtime\runs\frame_4c6e85faf3f24d38aa06fedb944b7c0d\summary.json |
| Outputs JSON | runtime_data\outputs\runtime\runs\frame_4c6e85faf3f24d38aa06fedb944b7c0d\outputs.json |
| Audit JSON | runtime_data\outputs\runtime\runs\frame_4c6e85faf3f24d38aa06fedb944b7c0d\audit.json |
| Run Report Markdown | runtime_data\outputs\runtime\runs\frame_4c6e85faf3f24d38aa06fedb944b7c0d\reports\run_report.md |
| Run Report HTML | runtime_data\outputs\runtime\runs\frame_4c6e85faf3f24d38aa06fedb944b7c0d\reports\run_report.html |
| Approval Pack Report Markdown | runtime_data\outputs\runtime\runs\frame_4c6e85faf3f24d38aa06fedb944b7c0d\reports\approval_pack_report.md |
| Approval Pack Report HTML | runtime_data\outputs\runtime\runs\frame_4c6e85faf3f24d38aa06fedb944b7c0d\reports\approval_pack_report.html |
| Failure Report Markdown | runtime_data\outputs\runtime\runs\frame_4c6e85faf3f24d38aa06fedb944b7c0d\reports\failure_report.md |
| Failure Report HTML | runtime_data\outputs\runtime\runs\frame_4c6e85faf3f24d38aa06fedb944b7c0d\reports\failure_report.html |
| Evidence Bundle JSON | runtime_data\outputs\runtime\runs\frame_4c6e85faf3f24d38aa06fedb944b7c0d\reports\evidence_bundle.json |
## 14. Raw References

- Frame ID: frame_4c6e85faf3f24d38aa06fedb944b7c0d
- Manifest ID: procurement.low_stock_reorder
- Runtime Data Dir: runtime_data\outputs\runtime
- Generated At: 2026-05-04T20:28:35Z
- Report Version: operator_run_report_v1