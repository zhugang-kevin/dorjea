"""依赖与境内模型版本巡检（不写境外服务域名）。"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry

TRACKED_PACKAGES = [
    "langgraph",
    "fastapi",
    "pydantic",
    "uvicorn",
    "httpx",
    "psutil",
    "pyyaml",
]

MODELS_REGISTRY = {
    "deepseek": {
        "current": "deepseek-chat",
        "family": "deepseek",
        "notes": "深度求索对话模型",
    },
    "moonshot": {
        "current": "moonshot-v1-8k",
        "family": "kimi",
        "notes": "月之暗面 Kimi",
    },
    "dashscope": {
        "current": "qwen-turbo",
        "family": "qwen",
        "notes": "通义千问兼容模式",
    },
    "zhipu": {
        "current": "glm-4-flash",
        "family": "glm",
        "notes": "智谱清言",
    },
}

VERSION_LOG = Path("logs") / "version_checks.jsonl"


def get_installed_version(package: str) -> str:
    """读取已安装的 Python 包版本。"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stdout.splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "unknown"


def get_latest_version(package: str) -> str:
    """尝试从 pip index 查询最新版本号。"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "index", "versions", package],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stdout.splitlines():
            if "Available versions:" in line:
                versions = line.split(":", 1)[1].strip().split(",")
                return versions[0].strip()
    except Exception:
        pass
    return "unknown"


def check_all_versions():
    """检查 TRACKED_PACKAGES 的安装与最新版本，并写入日志。"""
    results = []
    updates_available = []
    for pkg in TRACKED_PACKAGES:
        installed = get_installed_version(pkg)
        latest = get_latest_version(pkg)
        needs_update = installed != latest and latest != "unknown"
        if needs_update:
            updates_available.append(
                {"package": pkg, "installed": installed, "latest": latest}
            )
        results.append(
            {
                "package": pkg,
                "installed": installed,
                "latest": latest,
                "up_to_date": not needs_update,
            }
        )
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "packages_checked": len(results),
        "updates_available": len(updates_available),
        "updates": updates_available,
        "all_packages": results,
        "models_reference": MODELS_REGISTRY,
    }
    VERSION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(VERSION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False) + chr(10))
    write_audit_entry(
        AuditEntry(
            agent_id="version_checker",
            task_id="check",
            action="VERSION_CHECK_COMPLETE",
            details={"updates_available": len(updates_available)},
            success=True,
        )
    )
    return report


def print_version_report():
    """打印简要版本报告到标准输出。"""
    print("Checking versions...")
    report = check_all_versions()
    print("Packages checked: " + str(report["packages_checked"]))
    if report["updates_available"] == 0:
        print("All packages up to date.")
    else:
        print("Updates available: " + str(report["updates_available"]))
        for item in report["updates"]:
            print(
                "  "
                + item["package"]
                + ": "
                + item["installed"]
                + " -> "
                + item["latest"]
            )
    return report
