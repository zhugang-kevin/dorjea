"""校验 user_keys 模块存在；正式代码以 agents/meta_agent/user_keys.py 为准。"""
from pathlib import Path


def main() -> None:
    """确认用户密钥路由文件存在。"""
    path = Path("agents") / "meta_agent" / "user_keys.py"
    if not path.is_file():
        raise SystemExit("缺少 agents/meta_agent/user_keys.py")
    print("OK:", path)


if __name__ == "__main__":
    main()
