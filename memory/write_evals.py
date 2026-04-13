import json

tasks = [
    {
        "task_id": "eval_001",
        "request": "Create a research agent that finds and summarizes market trends for our strategy team.",
        "expected_department": "research",
        "expected_tools": ["web_search", "filesystem_server"],
        "min_responsibilities": 4
    },
    {
        "task_id": "eval_002",
        "request": "Create a coding agent that reviews Python code for bugs and suggests improvements.",
        "expected_department": "engineering",
        "expected_tools": ["filesystem_server", "github_server"],
        "min_responsibilities": 4
    },
    {
        "task_id": "eval_003",
        "request": "Create a marketing agent that writes email campaigns and tracks performance metrics.",
        "expected_department": "marketing",
        "expected_tools": ["filesystem_server"],
        "min_responsibilities": 4
    },
    {
        "task_id": "eval_004",
        "request": "Create a customer support agent that handles common product questions and escalates complex issues to humans.",
        "expected_department": "operations",
        "expected_tools": ["filesystem_server"],
        "min_responsibilities": 4
    },
    {
        "task_id": "eval_005",
        "request": "Create a data analysis agent that processes CSV files and generates insights reports.",
        "expected_department": "research",
        "expected_tools": ["filesystem_server"],
        "min_responsibilities": 4
    },
    {
        "task_id": "eval_006",
        "request": "Create a social media agent that drafts posts and suggests optimal posting schedules.",
        "expected_department": "marketing",
        "expected_tools": ["filesystem_server", "web_search"],
        "min_responsibilities": 4
    },
    {
        "task_id": "eval_007",
        "request": "Create a finance agent that monitors budgets and generates monthly expense summaries.",
        "expected_department": "finance",
        "expected_tools": ["filesystem_server"],
        "min_responsibilities": 4
    },
    {
        "task_id": "eval_008",
        "request": "Create a scheduling agent that manages meeting bookings and sends calendar invitations.",
        "expected_department": "operations",
        "expected_tools": ["filesystem_server"],
        "min_responsibilities": 4
    },
    {
        "task_id": "eval_009",
        "request": "Create a compliance agent that checks documents against regulatory requirements and flags violations.",
        "expected_department": "legal",
        "expected_tools": ["filesystem_server"],
        "min_responsibilities": 4
    },
    {
        "task_id": "eval_010",
        "request": "Create a knowledge management agent that organizes company documents and answers employee questions.",
        "expected_department": "hr",
        "expected_tools": ["filesystem_server", "web_search"],
        "min_responsibilities": 4
    }
]

with open("evals/datasets/meta_agent_tasks.jsonl", "w", encoding="utf-8") as f:
    for task in tasks:
        f.write(json.dumps(task) + "\n")

print("meta_agent_tasks.jsonl created with " + str(len(tasks)) + " tasks")
