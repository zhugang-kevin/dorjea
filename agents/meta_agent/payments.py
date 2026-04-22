"""
支付兼容层 — 元芯智能 AgentCore

境外 Stripe 已移除。实际收款请使用 payment_cn 与主应用路由：
POST /payment/wechat/create、POST /payment/alipay/create。
本文件保留历史函数签名，供 /payments/checkout 等端点导入。
"""
from __future__ import annotations

from datetime import datetime

from agents.meta_agent.auth import get_user, save_user
def create_checkout_session(user_email, plan, success_url, cancel_url):
    """不再创建 Stripe Checkout；返回错误说明，引导调用境内支付接口。"""
    _ = (user_email, plan, success_url, cancel_url)
    return None, (
        "境外卡收款已停用。请使用微信支付或支付宝："
        "POST /payment/wechat/create 或 POST /payment/alipay/create（请求体含 user_email、plan）。"
    )


def upgrade_user_plan(user_email, plan):
    user = get_user(user_email)
    if not user:
        return False, "User not found"
    user["plan"] = "professional" if plan == "pro" else plan
    user["plan_upgraded_at"] = datetime.utcnow().isoformat()
    save_user(user)
    return True, "Plan upgraded to " + plan


def handle_webhook(payload, sig_header):
    _ = (payload, sig_header)
    return False, "Stripe Webhook 已停用；请配置微信/支付宝异步通知（/payment/wechat/notify、/payment/alipay/notify）。"


def get_payment_config():
    return {
        "stripe_configured": False,
        "plans": {
            "professional": {"price_usd": 49, "price_cny": 199, "tokens_day": 50000},
            "business": {"price_usd": 199, "price_cny": 599, "tokens_day": 150000},
            "enterprise": {"price_usd": 999, "price_cny": 0, "tokens_day": 500000},
        },
        "cn_payment": {
            "wechat_native": True,
            "alipay_precreate": True,
            "endpoints": [
                "POST /payment/wechat/create",
                "POST /payment/alipay/create",
                "GET /payment/status/{order_id}",
            ],
        },
    }
