# Order Management Workflow Pack v1

Spec 110 adds a first-class order management workflow lane to TaskFrame.
All business logic lives in manifest steps and domain tools — none touches
the orchestrator.

---

## Workflows

| Manifest ID | Trigger event | Purpose |
|---|---|---|
| `order.validate_new` | `operator.order_validate_new` | Validate a new order: customer exists, items in stock, totals correct |
| `order.reserve_stock` | `operator.order_reserve_stock` | Prepare a stock reservation and stage it for operator approval |
| `order.release_paid` | `operator.order_release_paid` | Check payment status and stage a paid-order release for approval |
| `order.detect_delayed` | `operator.order_detect_delayed` | Detect orders whose estimated delivery date has passed |
| `order.update_shipment_status` | `operator.order_update_shipment_status` | Prepare a shipment status update and stage it for approval |

---

## Domain Tools (`runtime/order_management_tools.py`)

All tools follow the [tool result contract](tool_result_contract.md): every function
returns a dict with at least `ok: bool`. Side-effect tools are `dry_run=True` by
default and never write to production stores in the demo environment.

| Tool key | Side effect | Requires approval | Description |
|---|---|---|---|
| `order/validate_new` | No | No | Validate customer, items, and stock levels |
| `order/prepare_stock_reservation` | No | No | Stage a pending reservation action |
| `order/execute_stock_reservation` | Yes | Yes | Execute stock reservation (dry-run only) |
| `order/check_payment_status` | No | No | Look up payment records for an order |
| `order/prepare_release_paid_order` | No | No | Stage a pending release action if payment matched |
| `order/execute_release_paid_order` | Yes | Yes | Execute order release (dry-run only) |
| `order/detect_delayed_orders` | No | No | Scan shipments for overdue estimated delivery dates |
| `order/prepare_shipment_status_update` | No | No | Stage a pending shipment status action |
| `order/execute_shipment_status_update` | Yes | Yes | Execute shipment status update (dry-run only) |

### Prepare / Execute pattern

Side-effect operations use a two-step pattern:

1. **Prepare tool** — reads current state, validates inputs, returns a
   `pending_action` dict with `action_type`, `tool`, and `evidence`.
   Recorded in the run context as a pending action with `status=PENDING_APPROVAL`.
2. **Operator approval** — the operator reviews the pending action in the UI.
3. **Execute tool** — called with `dry_run=True` (the demo default); simulates
   the mutation and returns `before_*` / `after_*` evidence without writing to
   the business store.

This matches the same pending-action contract used by all other side-effect tools
in the runtime.

---

## Event Routes

Routes are defined in `config/event_routes.json` under `routes`:

```json
{ "route_id": "operator.order_validate_new",
  "source": "operator_scenario_pack",
  "event_type": "manual.order_validate_new",
  "manifest_id": "order.validate_new" }
```

Five routes are registered (one per workflow). All use
`source: "operator_scenario_pack"` so they appear in the operator UI scenario
browser and route alignment checks pass.

---

## Operator Scenarios

Ten scenarios are registered under the `order_management` category in
`src/operator_scenarios.py`:

| Scenario ID | Description |
|---|---|
| `order_validate_new_valid` | Validate a new order with sufficient stock |
| `order_validate_new_insufficient_stock` | Validate a new order where stock is zero |
| `order_reserve_stock` | Prepare stock reservation for a valid order |
| `order_release_paid` | Release an order whose payment is matched |
| `order_release_unpaid` | Attempt release for an order with no payment |
| `order_detect_delayed` | Detect delayed orders (returns at least one) |
| `order_update_shipment_status` | Update a shipment to shipped status |
| `order_reserve_stock_approve` | Approve and dry-run execute a stock reservation |
| `order_update_shipment_approve` | Approve and dry-run execute a shipment update |
| `order_check_payment_status` | Check payment status for an order |

---

## Business Dataset

Six test orders are seeded by `runtime/business_data.py`:

| Order ref | Customer | Status | Purpose |
|---|---|---|---|
| `ORD-10050` | CUST-1001 | pending_validation | Valid order, SKU-DESK-01 in stock |
| `ORD-10051` | CUST-1001 | pending_validation | Invalid order, SKU-CHAIR-01 zero stock |
| `ORD-10052` | CUST-1002 | awaiting_release | Payment matched (PAY-10052) |
| `ORD-10053` | CUST-1003 | awaiting_release | No payment — should block release |
| `ORD-10054` | CUST-1004 | released | SHIP-9010, estimated_delivery 2026-04-08 (delayed) |
| `ORD-10055` | CUST-1004 | released | SHIP-9011 packed, ready for status update |

---

## Running the Tests

```bash
# Spec 110 tests only
pytest tests/test_order_management_*.py -q

# Full suite
pytest -q
```

---

## Architectural Constraints

- No order management business logic may be added to the orchestrator
  (`runtime/orchestrator.py`).
- All reads go through `runtime/business_store.py`.
- Execute tools are blocked from live writes: `allow_live=False` in the
  tool registry; `dry_run=True` default in every execute function.
- Pending actions follow the standard approval contract defined in
  `docs/runtime_contracts.md`.
