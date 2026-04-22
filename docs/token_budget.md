# Token 配额说明 — 元芯智能

## 单次任务与每日上限

- Meta-Agent 创建智能体单次任务硬上限：**10,000 tokens**（原 20,000 减半）
- 系统每日令牌总预算（环境变量 `DAILY_TOKEN_BUDGET`）：**50,000 tokens**（原 100,000 减半）
- 单次任务环境上限（`MAX_TOKENS_PER_TASK`）：**10,000**

## 各角色预算（policy.yaml）

| 角色 | 每日/任务预算（tokens） |
|------|-------------------------|
| meta_agent | 10,000 |
| research_agent | 7,500 |
| coding_agent | 10,000 |
| marketing_agent | 5,000 |
| support_agent | 2,500 |
| daily_total（策略文件中的规划上限） | 50,000 |

## 套餐每日额度（与 `auth.PLAN_LIMITS` 一致）

| 套餐 | 每日 tokens |
|------|-------------|
| 免费版 | 5,000 |
| 专业版 | 50,000 |
| 商业版 | 150,000 |
| 企业版 | 500,000 |

## 监控

- 指标日志：`logs/metrics.jsonl`
- 健康检查：`GET /health`
- 用量概览：`GET /metrics`

## 规则

- 单次任务超过硬上限：中止并记录，需调整任务或提升配额策略
- 当日系统总预算用尽：相关 API 可返回 429，直至次日重置（以服务端策略为准）
