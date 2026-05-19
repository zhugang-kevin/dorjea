from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path


def _run_git(args: list[str], cwd: Path) -> str:
    try:
        out = subprocess.check_output(["git", *args], cwd=str(cwd), stderr=subprocess.STDOUT)
        return out.decode("utf-8", errors="replace").strip()
    except Exception:
        return "unknown"


def _status(value: bool) -> str:
    return "PASS" if value else "FAIL"


def _status_with_skip(passed: bool, skipped: bool) -> str:
    if skipped:
        return "SKIP"
    return _status(passed)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write release rehearsal report from gate results.")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=["standard", "release_candidate"], default="standard")
    parser.add_argument("--errors", type=int, required=True)
    parser.add_argument("--start-iso", required=True)
    parser.add_argument("--end-iso", required=True)
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--skip-clone-verify", action="store_true")
    parser.add_argument("--pytest-passed", action="store_true")
    parser.add_argument("--frontend-lint-passed", action="store_true")
    parser.add_argument("--frontend-build-passed", action="store_true")
    parser.add_argument("--clone-verify-passed", action="store_true")
    parser.add_argument("--api-health-passed", action="store_true")
    parser.add_argument("--db-check-passed", action="store_true")
    parser.add_argument("--backup-restore-passed", action="store_true")
    parser.add_argument("--assurance-passed", action="store_true")
    parser.add_argument("--imports-passed", action="store_true")
    parser.add_argument("--critical-files-passed", action="store_true")
    parser.add_argument("--todo-check-passed", action="store_true")
    parser.add_argument("--failure-cause", default="", help="Optional normalized failure cause code.")
    parser.add_argument("--sandbox-bypass-applied", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    start = dt.datetime.fromisoformat(args.start_iso)
    end = dt.datetime.fromisoformat(args.end_iso)
    duration = end - start

    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    commit = _run_git(["rev-parse", "--short", "HEAD"], repo_root)

    gate_backend_verify = (
        args.critical_files_passed
        and args.imports_passed
        and args.db_check_passed
        and args.assurance_passed
        and args.backup_restore_passed
        and args.todo_check_passed
    )
    gate_pytest = args.skip_pytest or args.pytest_passed
    gate_frontend = args.skip_frontend or (args.frontend_lint_passed and args.frontend_build_passed)
    gate_clone = args.skip_clone_verify or args.clone_verify_passed
    gate_api_health = args.api_health_passed
    overall_pass = args.errors == 0 and gate_backend_verify and gate_pytest and gate_frontend and gate_clone and gate_api_health

    report = {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "date": end.date().isoformat(),
        "owner": "Codex",
        "branch": branch,
        "commit": commit,
        "environment": "local",
        "mode": args.mode,
        "summary": {
            "result": _status(overall_pass),
            "start_time": args.start_iso,
            "end_time": args.end_iso,
            "duration_seconds": int(duration.total_seconds()),
            "errors": args.errors,
            "failure_cause": args.failure_cause or "",
            "sandbox_bypass_applied": args.sandbox_bypass_applied,
        },
        "hard_gates": {
            "backend_verification": {"status": _status(gate_backend_verify)},
            "pytest": {"status": _status_with_skip(gate_pytest, args.skip_pytest), "skipped": args.skip_pytest},
            "frontend": {
                "status": _status_with_skip(gate_frontend, args.skip_frontend),
                "skipped": args.skip_frontend,
                "lint_passed": args.frontend_lint_passed,
                "build_passed": args.frontend_build_passed,
            },
            "clone_verification": {"status": _status_with_skip(gate_clone, args.skip_clone_verify), "skipped": args.skip_clone_verify},
            "api_health": {"status": _status(gate_api_health)},
            "backup_restore": {"status": _status(args.backup_restore_passed)},
        },
        "checks": {
            "critical_files": args.critical_files_passed,
            "imports": args.imports_passed,
            "database": args.db_check_passed,
            "assurance": args.assurance_passed,
            "todo_scan": args.todo_check_passed,
        },
        "decision": "GO" if overall_pass else "NO-GO",
    }

    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"WROTE_REPORT: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
