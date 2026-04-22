"""境内微信支付 Native 与支付宝当面付（预下单二维码）；密钥均来自环境变量。"""
from __future__ import annotations

import base64
import json
import os
import secrets
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, Field

from agents.meta_agent.auth import get_user, save_user
from agents.meta_agent.billing import PLAN_DETAILS, PLAN_PRICES_CNY
from agents.meta_agent.notifications import send_payment_confirmation_email_zh

ORDERS_FILE = Path("memory") / "payment_orders.jsonl"
LEDGER_FILE = Path("memory") / "payment_ledger.jsonl"

PLAN_SLUG_ALIASES = {"pro": "professional"}


class WechatCreateRequest(BaseModel):
    """创建微信 Native 订单请求体。"""

    user_email: str = Field(..., min_length=3)
    plan: str = Field(..., description="professional | business | enterprise | pro")


class AlipayCreateRequest(BaseModel):
    """创建支付宝预下单请求体。"""

    user_email: str = Field(..., min_length=3)
    plan: str


def normalize_plan_slug(slug: str) -> str:
    """将 URL/表单中的套餐别名规范为 auth 使用的 plan 键。"""
    s = (slug or "").strip().lower()
    return PLAN_SLUG_ALIASES.get(s, s)


def plan_amount_cny(plan: str) -> float:
    """返回套餐对应人民币月费（企业版面议时为 0）。"""
    p = normalize_plan_slug(plan)
    if p == "free":
        return 0.0
    return float(PLAN_PRICES_CNY.get(p, 0) or 0)


def plan_name_zh(plan: str) -> str:
    """返回套餐中文展示名。"""
    p = normalize_plan_slug(plan)
    return str(PLAN_DETAILS.get(p, PLAN_DETAILS["free"]).get("name_zh", p))


def _ensure_memory() -> None:
    ORDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)


def _append_jsonl(path: Path, obj: dict) -> None:
    _ensure_memory()
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _load_all_orders() -> list[dict[str, Any]]:
    if not ORDERS_FILE.exists():
        return []
    rows: list[dict[str, Any]] = []
    with open(ORDERS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _save_orders(rows: list[dict[str, Any]]) -> None:
    _ensure_memory()
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def upsert_order(row: dict[str, Any]) -> None:
    """按 order_id 更新或追加订单。"""
    rows = _load_all_orders()
    now = datetime.utcnow().isoformat()
    for i, r in enumerate(rows):
        if r.get("order_id") == row.get("order_id"):
            merged = {**r, **row, "updated_at": now}
            rows[i] = merged
            _save_orders(rows)
            return
    row.setdefault("created_at", now)
    row.setdefault("updated_at", now)
    rows.append(row)
    _save_orders(rows)


def get_order_by_id(order_id: str) -> Optional[dict[str, Any]]:
    """按内部 order_id 查询。"""
    for r in _load_all_orders():
        if r.get("order_id") == order_id:
            return r
    return None


def get_order_by_out_trade_no(out_trade_no: str) -> Optional[dict[str, Any]]:
    """按商户订单号查询。"""
    for r in _load_all_orders():
        if r.get("out_trade_no") == out_trade_no:
            return r
    return None


def _ledger_paid(out_trade_no: str) -> bool:
    if not LEDGER_FILE.exists():
        return False
    with open(LEDGER_FILE, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                if (
                    rec.get("type") == "payment_success"
                    and rec.get("out_trade_no") == out_trade_no
                ):
                    return True
            except json.JSONDecodeError:
                continue
    return False


def _load_wechat_private_key():
    """加载微信支付商户私钥。"""
    pem = os.getenv("WECHAT_PRIVATE_KEY_PEM", "").replace("\\n", "\n")
    if pem.strip():
        return serialization.load_pem_private_key(
            pem.encode("utf-8"), password=None, backend=default_backend()
        )
    path = os.getenv("WECHAT_PRIVATE_KEY_PATH", "")
    if path and os.path.isfile(path):
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )
    return None


def _wechat_sign_message(private_key, message: str) -> str:
    sig = private_key.sign(
        message.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(sig).decode("utf-8")


def _wechat_authorization(
    private_key, mchid: str, serial: str, method: str, url_path: str, body: str
) -> str:
    ts = str(int(time.time()))
    nonce = secrets.token_hex(16)
    sign_str = f"{method}\n{url_path}\n{ts}\n{nonce}\n{body}\n"
    signature = _wechat_sign_message(private_key, sign_str)
    return (
        "WECHATPAY2-SHA256-RSA2048 "
        f'mchid="{mchid}",nonce_str="{nonce}",timestamp="{ts}",'
        f'serial_no="{serial}",signature="{signature}"'
    )


def wechat_native_create(req: WechatCreateRequest) -> dict:
    """调用微信 v3 Native 下单，返回 code_url 与内部 order_id。"""
    try:
        plan = normalize_plan_slug(req.plan)
        if plan not in ("professional", "business", "enterprise"):
            return {"success": False, "error": "套餐类型无效，请选择专业版、商业版或企业版。"}
        amount_cny = plan_amount_cny(plan)
        if amount_cny <= 0:
            return {"success": False, "error": "该套餐无需在线支付或价格为面议。"}
        mchid = os.getenv("WECHAT_MCHID", "")
        appid = os.getenv("WECHAT_APPID", "")
        serial = os.getenv("WECHAT_CERT_SERIAL", "")
        v3key = os.getenv("WECHAT_API_V3_KEY", "")
        base = os.getenv("PUBLIC_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        notify_url = os.getenv("WECHAT_NOTIFY_URL", "").strip() or (
            base + "/payment/wechat/notify"
        )
        pk = _load_wechat_private_key()
        if not all([mchid, appid, serial, v3key, pk]):
            return {
                "success": False,
                "error": "微信支付环境变量未配置完整（WECHAT_MCHID、WECHAT_APPID、WECHAT_CERT_SERIAL、WECHAT_API_V3_KEY、私钥 PEM 或路径）。",
            }
        amount_fen = int(round(amount_cny * 100))
        out_trade_no = "WX" + time.strftime("%Y%m%d%H%M%S") + secrets.token_hex(4)
        order_id = secrets.token_urlsafe(12)
        body_obj = {
            "appid": appid,
            "mchid": mchid,
            "description": plan_name_zh(plan) + " 套餐",
            "out_trade_no": out_trade_no,
            "notify_url": notify_url,
            "amount": {"total": amount_fen, "currency": "CNY"},
        }
        body = json.dumps(body_obj, ensure_ascii=False)
        url_path = "/v3/pay/transactions/native"
        auth = _wechat_authorization(pk, mchid, serial, "POST", url_path, body)
        headers = {
            "Authorization": auth,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                "https://api.mch.weixin.qq.com" + url_path, content=body, headers=headers
            )
        if resp.status_code >= 400:
            return {
                "success": False,
                "error": f"微信下单失败：HTTP {resp.status_code} {resp.text[:500]}",
            }
        data = resp.json()
        code_url = data.get("code_url", "")
        if not code_url:
            return {"success": False, "error": "微信返回缺少 code_url：" + resp.text[:400]}
        now = datetime.utcnow().isoformat()
        upsert_order(
            {
                "order_id": order_id,
                "provider": "wechat",
                "out_trade_no": out_trade_no,
                "user_email": req.user_email.lower().strip(),
                "plan": plan,
                "amount_fen": amount_fen,
                "status": "pending",
                "code_url": code_url,
                "created_at": now,
                "updated_at": now,
            }
        )
        return {
            "success": True,
            "order_id": order_id,
            "out_trade_no": out_trade_no,
            "code_url": code_url,
            "amount_cny": amount_cny,
            "redirect_after_success_hint": "/dashboard/account",
        }
    except Exception as exc:
        return {"success": False, "error": f"创建微信订单异常：{exc!s}"}


def wechat_query_status(out_trade_no: str) -> dict:
    """按商户订单号查询微信支付状态。"""
    try:
        mchid = os.getenv("WECHAT_MCHID", "")
        serial = os.getenv("WECHAT_CERT_SERIAL", "")
        pk = _load_wechat_private_key()
        if not pk or not mchid:
            return {"ok": False, "error": "微信支付未配置，无法查询。"}
        url_path = f"/v3/pay/transactions/out-trade-no/{out_trade_no}?mchid={mchid}"
        auth = _wechat_authorization(pk, mchid, serial, "GET", url_path, "")
        headers = {"Authorization": auth, "Accept": "application/json"}
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(
                "https://api.mch.weixin.qq.com" + url_path, headers=headers
            )
        if resp.status_code >= 400:
            return {"ok": False, "error": f"查询失败：{resp.status_code} {resp.text[:400]}"}
        return {"ok": True, "data": resp.json()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def wechat_decrypt_notify_resource(resource: dict) -> dict:
    """解密微信 v3 支付通知 resource 字段。"""
    ciphertext = resource.get("ciphertext", "")
    nonce = resource.get("nonce", "")
    associated = resource.get("associated_data", "")
    key = os.getenv("WECHAT_API_V3_KEY", "").encode("utf-8")
    if len(key) != 32:
        raise ValueError("WECHAT_API_V3_KEY 长度须为 32 字节")
    data = base64.b64decode(ciphertext)
    aes = AESGCM(key)
    plain = aes.decrypt(nonce.encode("utf-8"), data, associated.encode("utf-8"))
    return json.loads(plain.decode("utf-8"))


def finalize_paid_order(
    user_email: str, plan: str, provider: str, out_trade_no: str, amount_fen: int
) -> None:
    """验单成功后升级用户套餐、记账并发中文确认邮件。"""
    if _ledger_paid(out_trade_no):
        return
    user = get_user(user_email)
    if not user:
        return
    user["plan"] = normalize_plan_slug(plan)
    user["plan_upgraded_at"] = datetime.utcnow().isoformat()
    user["payment_method"] = provider
    save_user(user)
    _append_jsonl(
        LEDGER_FILE,
        {
            "type": "payment_success",
            "user_email": user_email,
            "plan": user["plan"],
            "provider": provider,
            "out_trade_no": out_trade_no,
            "amount_fen": amount_fen,
            "at": datetime.utcnow().isoformat(),
        },
    )
    name = str(user.get("name", user_email))
    send_payment_confirmation_email_zh(
        user_email,
        name,
        plan_name_zh(user["plan"]),
        amount_fen / 100.0,
        order_id=out_trade_no,
    )


def _mark_order_success(row: dict[str, Any], detail: dict[str, Any]) -> None:
    if row.get("status") == "success":
        return
    row["status"] = "success"
    row["paid_detail"] = detail
    upsert_order(row)
    finalize_paid_order(
        row["user_email"],
        row["plan"],
        str(row.get("provider", "")),
        str(row.get("out_trade_no", "")),
        int(row.get("amount_fen", 0)),
    )


def wechat_handle_notify(body_json: dict) -> dict:
    """处理微信支付异步通知 JSON 体，返回微信要求的应答结构。"""
    try:
        event_type = body_json.get("event_type", "")
        resource = body_json.get("resource") or {}
        if event_type != "TRANSACTION.SUCCESS":
            return {"code": "SUCCESS", "message": "忽略"}
        plain = wechat_decrypt_notify_resource(resource)
        out_trade_no = plain.get("out_trade_no", "")
        trade_state = plain.get("trade_state", "")
        if trade_state != "SUCCESS":
            return {"code": "SUCCESS", "message": "非成功状态"}
        row = get_order_by_out_trade_no(out_trade_no)
        if not row:
            return {"code": "FAIL", "message": "订单不存在"}
        _mark_order_success(row, plain)
        return {"code": "SUCCESS", "message": "成功"}
    except Exception as exc:
        return {"code": "FAIL", "message": f"处理异常：{exc!s}"}


def _load_rsa_private_key_from_pem(pem: str):
    return serialization.load_pem_private_key(
        pem.encode("utf-8"), password=None, backend=default_backend()
    )


def _load_rsa_public_key_from_pem(pem: str):
    return serialization.load_pem_public_key(
        pem.encode("utf-8"), backend=default_backend()
    )


def _alipay_sign_params(params: dict[str, str], private_key) -> str:
    pairs = []
    for k in sorted(params.keys()):
        if k in ("sign", "sign_type"):
            continue
        v = params[k]
        if v is None or v == "":
            continue
        pairs.append(f"{k}={v}")
    data = "&".join(pairs)
    sig = private_key.sign(
        data.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256()
    )
    return base64.b64encode(sig).decode("utf-8")


def _alipay_gateway_post(params: dict[str, str]) -> dict[str, Any]:
    gateway = os.getenv("ALIPAY_GATEWAY", "https://openapi.alipay.com/gateway.do")
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(gateway, data=params)
    resp.raise_for_status()
    j = resp.json()
    key = "alipay_trade_precreate_response"
    if key not in j:
        return {"_raw": j}
    inner = j[key]
    return inner if isinstance(inner, dict) else json.loads(inner)


def alipay_precreate(req: AlipayCreateRequest) -> dict:
    """支付宝当面付预下单，返回 qr_code 字符串供生成二维码。"""
    try:
        plan = normalize_plan_slug(req.plan)
        if plan not in ("professional", "business", "enterprise"):
            return {"success": False, "error": "套餐类型无效。"}
        amount_cny = plan_amount_cny(plan)
        if amount_cny <= 0:
            return {"success": False, "error": "该套餐无需在线支付或价格为面议。"}
        app_id = os.getenv("ALIPAY_APP_ID", "")
        priv_pem = os.getenv("ALIPAY_APP_PRIVATE_KEY_PEM", "").replace("\\n", "\n")
        if not priv_pem.strip() and os.getenv("ALIPAY_APP_PRIVATE_KEY_PATH"):
            with open(
                os.environ["ALIPAY_APP_PRIVATE_KEY_PATH"], encoding="utf-8"
            ) as f:
                priv_pem = f.read()
        if not app_id or not priv_pem.strip():
            return {
                "success": False,
                "error": "支付宝未配置：ALIPAY_APP_ID 与 ALIPAY_APP_PRIVATE_KEY_PEM（或路径）。",
            }
        priv = _load_rsa_private_key_from_pem(priv_pem)
        base = os.getenv("PUBLIC_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        notify_url = os.getenv("ALIPAY_NOTIFY_URL", "").strip() or (
            base + "/payment/alipay/notify"
        )
        out_trade_no = "ALI" + time.strftime("%Y%m%d%H%M%S") + secrets.token_hex(4)
        order_id = secrets.token_urlsafe(12)
        biz = {
            "out_trade_no": out_trade_no,
            "total_amount": f"{amount_cny:.2f}",
            "subject": plan_name_zh(plan),
        }
        params: dict[str, str] = {
            "app_id": app_id,
            "method": "alipay.trade.precreate",
            "format": "JSON",
            "charset": "utf-8",
            "sign_type": "RSA2",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "notify_url": notify_url,
            "biz_content": json.dumps(biz, ensure_ascii=False, separators=(",", ":")),
        }
        params["sign"] = _alipay_sign_params(params, priv)
        inner = _alipay_gateway_post(params)
        if inner.get("code") != "10000":
            return {
                "success": False,
                "error": "支付宝预下单失败："
                + json.dumps(inner, ensure_ascii=False)[:500],
            }
        qr = inner.get("qr_code", "")
        amount_fen = int(round(amount_cny * 100))
        now = datetime.utcnow().isoformat()
        upsert_order(
            {
                "order_id": order_id,
                "provider": "alipay",
                "out_trade_no": out_trade_no,
                "user_email": req.user_email.lower().strip(),
                "plan": plan,
                "amount_fen": amount_fen,
                "status": "pending",
                "code_url": qr,
                "created_at": now,
                "updated_at": now,
            }
        )
        return {
            "success": True,
            "order_id": order_id,
            "out_trade_no": out_trade_no,
            "code_url": qr,
            "amount_cny": amount_cny,
            "redirect_after_success_hint": "/dashboard/account",
        }
    except Exception as exc:
        return {"success": False, "error": f"创建支付宝订单异常：{exc!s}"}


def alipay_verify_notify(form: dict[str, str]) -> bool:
    """校验支付宝异步通知 RSA2 签名。"""
    try:
        pub_pem = os.getenv("ALIPAY_ALIPAY_PUBLIC_KEY_PEM", "").replace("\\n", "\n")
        if not pub_pem.strip() and os.getenv("ALIPAY_ALIPAY_PUBLIC_KEY_PATH"):
            with open(
                os.environ["ALIPAY_ALIPAY_PUBLIC_KEY_PATH"], encoding="utf-8"
            ) as f:
                pub_pem = f.read()
        if not pub_pem.strip():
            return False
        pub = _load_rsa_public_key_from_pem(pub_pem)
        sign = form.get("sign", "")
        sign_type = form.get("sign_type", "RSA2")
        if sign_type != "RSA2":
            return False
        verify_params = {k: v for k, v in form.items() if k not in ("sign", "sign_type")}
        pairs = []
        for k in sorted(verify_params.keys()):
            v = verify_params[k]
            if v is None or v == "":
                continue
            pairs.append(f"{k}={v}")
        message = "&".join(pairs)
        sig_bytes = base64.b64decode(sign)
        pub.verify(
            sig_bytes,
            message.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def alipay_handle_notify(form_dict: dict[str, str]) -> str:
    """处理支付宝 notify_url 表单，返回 success 或 fail 纯文本。"""
    try:
        if not alipay_verify_notify(form_dict):
            return "fail"
        if form_dict.get("trade_status") != "TRADE_SUCCESS":
            return "success"
        out_trade_no = form_dict.get("out_trade_no", "")
        row = get_order_by_out_trade_no(out_trade_no)
        if not row:
            return "fail"
        _mark_order_success(row, dict(form_dict))
        return "success"
    except Exception:
        return "fail"


def payment_status(order_id: str) -> dict[str, Any]:
    """查询内部订单状态；微信订单可顺带向微信拉取最新 trade_state。"""
    row = get_order_by_id(order_id)
    if not row:
        return {"found": False, "error": "订单不存在"}
    if row.get("status") == "success":
        return {"found": True, "status": "success", "order": row}
    if row.get("provider") == "wechat":
        q = wechat_query_status(str(row["out_trade_no"]))
        if not q.get("ok"):
            return {
                "found": True,
                "status": row.get("status"),
                "query_error": q.get("error"),
                "order": row,
            }
        trade_state = (q.get("data") or {}).get("trade_state", "")
        if trade_state == "SUCCESS":
            fresh = get_order_by_out_trade_no(str(row["out_trade_no"]))
            if fresh:
                _mark_order_success(fresh, q.get("data") or {})
            row = get_order_by_id(order_id) or row
        return {
            "found": True,
            "status": row.get("status"),
            "trade_state": trade_state,
            "order": row,
        }
    return {
        "found": True,
        "status": row.get("status"),
        "order": row,
        "note": "支付宝订单请依赖异步通知；也可扩展主动查询接口。",
    }


def poll_wechat_payment_blocking(out_trade_no: str) -> bool:
    """每 3 秒查询一次微信订单，最多约 5 分钟。"""
    for _ in range(100):
        q = wechat_query_status(out_trade_no)
        if q.get("ok") and (q.get("data") or {}).get("trade_state") == "SUCCESS":
            row = get_order_by_out_trade_no(out_trade_no)
            if row:
                _mark_order_success(row, q.get("data") or {})
            return True
        time.sleep(3)
    return False
