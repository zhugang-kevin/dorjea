# 前后端路由映射（节选）

前端为 Next.js（`AgentCore-dashboard/app`），后端为 FastAPI（`agents/meta_agent/api.py` 及各 `APIRouter`）。以下为主要对应关系；健康检查、支付回调等仅后端暴露。

| 前端路径 | 说明 | 主要后端 API |
|---------|------|----------------|
| `/login` | 登录注册 | `POST /auth/login`, `POST /auth/register` |
| `/dashboard` | 控制台 | `GET /health`, `GET /agents`, `POST /agents/create`, `POST /agents/{name}/run`, `GET /system/budget` |
| `/pricing` | 定价 | `GET /plans`, `GET /billing/plans/catalog` |
| `/billing` | 订阅与账单 | `billing` 路由前缀 `/billing` |
| `/account` | 账户 | `GET /auth/me` |
| `/api-keys` | API 密钥 | `/api-keys/*` |
| `/user-keys` | AI 服务密钥 | `/user-keys/*` |
| `/memory` | 记忆库 | `/memory/*` |
| `/tools` | 工具集成 | `/tools/*` |
| `/workflows` | 工作流 | `/workflows/*` |
| `/workflow-builder` | 可视化编排（前端） | 同上工作流 API |
| `/analytics` | 数据分析 | `/analytics/*` |
| `/clones` | 部门克隆 | `/clones/*` |
| `/leaderboard` | 排行榜 | `/leaderboard/*` |
| `/monitor` | 监控 | `/monitor/*` |
| `/support` | 客服 | `support` 路由 |
| `/affiliate` | 推荐 | `/affiliate/*` |
| `/payment` | 支付页 | `POST /payment/wechat/create`, `POST /payment/alipay/create`, `GET /payment/status/{order_id}` |

未在上表列出的静态页（隐私、条款、帮助等）以内容展示为主，可不绑定独立 REST 资源。
