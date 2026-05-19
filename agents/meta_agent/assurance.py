from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from agents.meta_agent.audit_logger import LOG_PATH, verify_audit_chain
from agents.meta_agent.build_contract import COMPLETE_PHASE, load_build_state
from agents.runtime.ai_clients import configured_model_providers, provider_has_credentials

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
DB_PATH = REPO_ROOT / "memory" / "aifactory.db"
PROJECT_STATE_PATH = REPO_ROOT / "ai-system" / "project_state.json"
BACKUP_ROOT = REPO_ROOT / "memory" / "backups"
SUPPORTED_QUEUE_BACKENDS = {"filesystem"}


def _bool_env(name: str, default: bool = False) -> bool:
    value = str(os.getenv(name, "")).strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_database() -> tuple[bool, str]:
    if not DB_PATH.exists():
        return False, f"Database missing: {DB_PATH}"
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return True, ""
    except sqlite3.Error as exc:
        return False, f"Database unreadable: {exc}"


def _check_project_state() -> tuple[bool, str]:
    if not PROJECT_STATE_PATH.exists():
        return False, f"Project state missing: {PROJECT_STATE_PATH}"
    state = load_build_state()
    if state.get("current_phase") != COMPLETE_PHASE:
        return False, f"Build state is not complete: {state.get('current_phase')}"
    return True, ""


def _check_audit_chain() -> tuple[bool, str, dict]:
    audit = verify_audit_chain()
    if not audit.get("valid"):
        return False, audit.get("error", "audit chain invalid"), audit
    if int(audit.get("legacy_prefix_records", 0) or 0) != 0:
        return False, "audit chain still has legacy prefix records", audit
    return True, "", audit


def _check_queue_backend() -> tuple[bool, str]:
    backend = str(os.getenv("TASK_QUEUE_BACKEND", "filesystem")).strip().lower()
    if backend not in SUPPORTED_QUEUE_BACKENDS:
        return False, f"Unsupported queue backend: {backend}"
    queue_path = Path(os.getenv("TASK_QUEUE_PATH", str(REPO_ROOT / "memory" / "task_queue")))
    if backend == "filesystem" and not queue_path.exists():
        return False, f"Queue path missing: {queue_path}"
    return True, ""


def _check_model_backends() -> tuple[bool, list[str], dict]:
    failures: list[str] = []
    primary = str(os.getenv("PRIMARY_CHAT_BACKEND", "deepseek")).strip().lower()
    verifier = str(os.getenv("VERIFIER_CHAT_BACKEND", "deepseek")).strip().lower()
    configured = configured_model_providers()
    if not provider_has_credentials(primary):
        failures.append(f"Primary backend missing credentials: {primary}")
    if not provider_has_credentials(verifier):
        failures.append(f"Verifier backend missing credentials: {verifier}")
    details = {
        "configured_providers": configured,
        "primary_backend": primary,
        "primary_backend_ready": provider_has_credentials(primary),
        "verifier_backend": verifier,
        "verifier_backend_ready": provider_has_credentials(verifier),
    }
    return not failures, failures, details


def _check_jwt_secret() -> tuple[bool, str]:
    env = str(os.getenv("ENVIRONMENT", "development")).strip().lower()
    secret = str(os.getenv("JWT_SECRET_KEY", ""))
    if len(secret) < 32:
        return False, "JWT secret is too short"
    if env in {"production", "prod"} and secret == "dev-only-change-me":
        return False, "Production cannot use the development JWT secret"
    return True, ""


def assurance_status() -> dict:
    failures: list[str] = []

    db_ok, db_error = _check_database()
    if not db_ok:
        failures.append(db_error)

    build_ok, build_error = _check_project_state()
    if not build_ok:
        failures.append(build_error)

    audit_ok, audit_error, audit = _check_audit_chain()
    if not audit_ok:
        failures.append(audit_error)

    queue_ok, queue_error = _check_queue_backend()
    if not queue_ok:
        failures.append(queue_error)

    models_ok, model_failures, model_details = _check_model_backends()
    failures.extend(model_failures)

    jwt_ok, jwt_error = _check_jwt_secret()
    if not jwt_ok:
        failures.append(jwt_error)

    status = "pass" if not failures else "fail"
    return {
        "status": status,
        "environment": str(os.getenv("ENVIRONMENT", "development")),
        "failures": failures,
        "checks": {
            "database": db_ok,
            "build_state_complete": build_ok,
            "audit_chain_valid": audit_ok,
            "queue_backend_valid": queue_ok,
            "model_backends_ready": models_ok,
            "jwt_secret_safe": jwt_ok,
        },
        "models": model_details,
        "audit_chain": audit,
        "fail_closed_enabled": _bool_env("ASSURANCE_FAIL_CLOSED", False),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def enforce_startup_assurance() -> dict:
    status = assurance_status()
    if status["status"] != "pass" and status["fail_closed_enabled"]:
        raise RuntimeError("Startup assurance failed: " + " | ".join(status["failures"]))
    return status


def create_runtime_backup() -> dict:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    # Include sub-second precision to avoid collisions when multiple checks run
    # in the same second (for example parallel verification runs).
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup_dir = BACKUP_ROOT / f"assurance_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)

    copied: list[dict] = []
    for source in [DB_PATH, PROJECT_STATE_PATH, LOG_PATH]:
        if not source.exists():
            continue
        target = backup_dir / source.name
        shutil.copy2(source, target)
        copied.append(
            {
                "name": source.name,
                "size": target.stat().st_size,
                "sha256": _sha256(target),
            }
        )

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(REPO_ROOT),
        "files": copied,
    }
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"backup_dir": str(backup_dir), "manifest_path": str(manifest_path), "files": copied}


def verify_backup_restore() -> dict:
    backup = create_runtime_backup()
    backup_dir = Path(backup["backup_dir"])
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    failures: list[str] = []

    for file_info in manifest.get("files", []):
        candidate = backup_dir / str(file_info["name"])
        if not candidate.exists():
            failures.append(f"Backup file missing: {candidate.name}")
            continue
        if _sha256(candidate) != str(file_info["sha256"]):
            failures.append(f"Hash mismatch: {candidate.name}")

    db_copy = backup_dir / DB_PATH.name
    if db_copy.exists():
        try:
            conn = sqlite3.connect(db_copy)
            conn.execute("SELECT 1").fetchone()
            conn.close()
        except sqlite3.Error as exc:
            failures.append(f"Backup DB unreadable: {exc}")

    state_copy = backup_dir / PROJECT_STATE_PATH.name
    if state_copy.exists():
        try:
            copied_state = json.loads(state_copy.read_text(encoding="utf-8"))
            if copied_state.get("current_phase") != COMPLETE_PHASE:
                failures.append("Backup project_state is not complete")
        except json.JSONDecodeError as exc:
            failures.append(f"Backup project_state invalid JSON: {exc}")

    return {
        "status": "pass" if not failures else "fail",
        "failures": failures,
        "backup": backup,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
