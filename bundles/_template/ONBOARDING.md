# Onboarding Record — <CUSTOMER>

The engagement record for this customer bundle. Fill in as you go; it is the audit trail of
what was configured, why, and who signed off. Keep it in the bundle.

- **Customer:** <name>
- **Engagement owner:** <you>
- **Start date:** <YYYY-MM-DD>
- **Core image version:** taskframe-runtime:<version>
- **Deployment target:** on-prem / self-hosted by customer

---

## 1. Scope — workflows to automate

| # | Workflow | Manifest id | Status |
|---|----------|-------------|--------|
| 1 |          |             | draft / validated / live |

## 2. Tools required

| Workflow | Action needed | Pack (core/custom) | Pack id | Live creds? |
|----------|---------------|--------------------|---------|-------------|
|          |               |                    |         | no          |

## 3. Tool packs enabled

List what's in `config/enabled_toolpacks.json` and the gate result for each.

| Pack id | core/custom | Contract test | Governance | Health |
|---------|-------------|---------------|-----------|--------|
| core_business | core | n/a (built-in) | pass | pass |
|         |             |               |           |        |

## 4. Credentials provisioned

| Tool family | Provisioned? | Location | Notes |
|-------------|--------------|----------|-------|
| Backend auth tokens | [ ] | .env | admin/operator/viewer |
| Google (Sheets/Gmail/Calendar) | [ ] | config/google/ | only if used |
| Accounting sheet | [ ] | config/accounting_google_sheet.json | only if used |
| RPA / browser | [ ] | per profile | only if used |

## 5. Gate results (must all pass before pilot)

- [ ] All custom packs pass the tool-pack contract runner.
- [ ] All custom packs pass governance + health checks.
- [ ] All manifests pass strict-contract validation.
- [ ] Manifest catalog health clean (no errors).
- [ ] Each manifest dry-run succeeds.
- [ ] `taskframe pilot-readiness --write-pack` ≥ threshold (attach pack path below).
- [ ] `/api/health` returns `ok: true` and `runtime_live_mode: false`.
- [ ] Backend auth ON, dev bypass OFF, tokens are strong and unique.

Pilot-readiness pack: `<runtime_data path>`

## 6. Live actions (if any)

A read-only pilot enables none. If a specific live action is approved for this engagement,
record it here with the approval and the guardrail relied upon (see
docs/live_execution_safety.md). Default: none.

| Live action | Approved by | Date | Guardrail |
|-------------|-------------|------|-----------|
| none        |             |      |           |

## 7. Sign-off

- [ ] Engagement owner: <name> — <date>
- [ ] Customer contact: <name> — <date>

## 8. Change log

| Date | Change | By |
|------|--------|----|
|      | bundle created from _template |  |
