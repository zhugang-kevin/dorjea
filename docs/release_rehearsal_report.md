# Release Rehearsal Report

Date: YYYY-MM-DD  
Owner:  
Branch/Commit:  
Environment: local / staging / production-like

## 1. Rehearsal Summary

- Result: PASS / FAIL
- Start time:
- End time:
- Duration:

## 2. Hard Gate Results

1. Backend verification (`scripts/verify.ps1`)
- Command run:
- Exit code:
- Key output:
- Status: PASS / FAIL

2. Backend tests (`pytest -q`)
- Command run:
- Exit code:
- Passed/Failed count:
- Status: PASS / FAIL

3. API health (`/health`)
- Method:
- HTTP status:
- Response summary:
- Status: PASS / FAIL

4. Frontend lint/build (`frontend`)
- Lint command/exit:
- Build command/exit:
- Status: PASS / FAIL

5. Clone verification (`clone_verify.ps1`)
- Command run:
- Exit code:
- Clone summary:
- Status: PASS / FAIL

6. Backup/restore verification
- Command run:
- Exit code:
- Restore summary:
- Status: PASS / FAIL

## 3. Soft Gate Review

1. Transient warnings
- Warning:
- Impact:
- Owner:
- Due date:
- Decision: ACCEPT / MITIGATE BEFORE RELEASE

2. Other warnings
- Warning:
- Impact:
- Owner:
- Due date:
- Decision: ACCEPT / MITIGATE BEFORE RELEASE

## 4. Regression Checks

- Any newly failing tests:
- Any new lint/type issues:
- Any route/feature broken after fixes:

## 5. Risk Ledger

1. Risk:
- Severity: LOW / MEDIUM / HIGH
- Mitigation:
- Owner:
- Due date:

2. Risk:
- Severity: LOW / MEDIUM / HIGH
- Mitigation:
- Owner:
- Due date:

## 6. Go/No-Go Decision

- Decision: GO / NO-GO
- Reason:
- Final approver:
- Approval timestamp:

