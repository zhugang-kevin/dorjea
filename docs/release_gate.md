# Release Gate (Aggressive Execution Baseline)

This document defines hard, measurable go/no-go criteria for production readiness in this repository.

## Scope

- Backend runtime (`AgentCore`)
- Frontend dashboard (`AgentCore/frontend`)
- Department clones (`AgentCore_*`)
- Data safety and recovery checks

## Gate Types

1. Hard Gate:
   Must pass. Any failure is a release stop.
2. Soft Gate:
   Must be reviewed with owner sign-off before release.

## Hard Gates (Must Pass)

1. Backend verification
- Command: `.\scripts\verify.ps1`
- Pass criteria:
  - Exit code `0`
  - No `FAILED:` lines
  - No missing critical files

2. Backend tests
- Command: `venv\Scripts\python.exe -m pytest -q`
- Pass criteria:
  - Exit code `0`
  - All tests pass
  - No import/collection errors

3. API health
- Command:
  - Local test client or live check to `/health`
- Pass criteria:
  - HTTP `200`
  - Response status is healthy/ok

4. Frontend quality
- Commands:
  - `cd frontend`
  - `npm run lint`
  - `npm run build`
- Pass criteria:
  - Lint exit code `0`
  - Build exit code `0`
  - No unresolved TypeScript compile failures

5. Clone consistency
- Command: `cd ..\ ; .\clone_verify.ps1`
- Pass criteria:
  - Exit code `0`
  - All clone critical-file checks pass
  - All clone import checks pass

6. Backup and restore viability
- Command: `venv\Scripts\python.exe scripts\backup_restore_verify.py`
- Pass criteria:
  - Exit code `0`
  - Restore reports valid schema and core table availability

## Soft Gates (Require Explicit Risk Sign-off)

1. DB lock/transient warning in clone verification
- Condition:
  - `database is locked` or equivalent transient lock warning appears.
- Requirement:
  - Must be documented in rehearsal report with timestamp and owner.

2. Non-blocking operational warnings
- Condition:
  - Any warning not covered by hard gates.
- Requirement:
  - Explicit mitigation owner and due date.

## Minimum Evidence Package For Release

Release candidate is valid only when all of these exist:

1. Latest command transcript snippets (or CI logs) for:
- `scripts/verify.ps1`
- `pytest`
- `frontend lint/build`
- `clone_verify.ps1`
- `backup_restore_verify.py`

2. Completed release rehearsal report:
- `docs/release_rehearsal_report.md`

3. Risk ledger section with:
- unresolved risks
- owner
- mitigation date

## Stop Conditions (Automatic No-Go)

1. Any hard gate fails.
2. Any auth or plan-enforcement test fails.
3. Build succeeds only by disabling core checks without documented approval.
4. Backup/restore validation fails.

## Ownership and Approval

1. Technical execution owner:
- Codex implementation lane

2. Governance owner:
- Human project owner/founder

3. Final release approval:
- Human owner only, after all hard gates pass and soft-gate risks are signed.

