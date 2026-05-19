from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a markdown summary from a rehearsal JSON report.")
    parser.add_argument("--input", required=True, help="Path to rehearsal JSON report.")
    parser.add_argument("--output", required=True, help="Path to output markdown summary.")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report = json.loads(input_path.read_text(encoding="utf-8"))

    summary = report.get("summary", {})
    hard = report.get("hard_gates", {})
    checks = report.get("checks", {})
    mode = report.get("mode", "standard")

    lines = [
        "# Release Rehearsal Summary",
        "",
        f"- Date: `{report.get('date', 'unknown')}`",
        f"- Branch/Commit: `{report.get('branch', 'unknown')}` / `{report.get('commit', 'unknown')}`",
        f"- Environment: `{report.get('environment', 'unknown')}`",
        f"- Mode: `{mode}`",
        f"- Result: **{summary.get('result', 'UNKNOWN')}**",
        f"- Decision: **{report.get('decision', 'UNKNOWN')}**",
        f"- Duration (sec): `{summary.get('duration_seconds', 'unknown')}`",
        f"- Errors: `{summary.get('errors', 'unknown')}`",
        "",
        "## Hard Gates",
        "",
        f"- Backend verification: `{hard.get('backend_verification', {}).get('status', 'UNKNOWN')}`",
        f"- Pytest: `{hard.get('pytest', {}).get('status', 'UNKNOWN')}`",
        f"- Frontend: `{hard.get('frontend', {}).get('status', 'UNKNOWN')}` (skipped: `{hard.get('frontend', {}).get('skipped', False)}`)",
        f"- API health: `{hard.get('api_health', {}).get('status', 'UNKNOWN')}`",
        f"- Clone verification: `{hard.get('clone_verification', {}).get('status', 'UNKNOWN')}` (skipped: `{hard.get('clone_verification', {}).get('skipped', False)}`)",
        f"- Backup/restore: `{hard.get('backup_restore', {}).get('status', 'UNKNOWN')}`",
        "",
        "## Check Details",
        "",
        f"- Critical files: `{checks.get('critical_files', False)}`",
        f"- Imports: `{checks.get('imports', False)}`",
        f"- Database: `{checks.get('database', False)}`",
        f"- Assurance: `{checks.get('assurance', False)}`",
        f"- TODO scan: `{checks.get('todo_scan', False)}`",
        "",
        "## Evidence",
        "",
        f"- Source report: `{input_path}`",
    ]

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE_SUMMARY: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
