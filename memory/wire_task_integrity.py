with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from agents.meta_agent.task_gateway import gateway"
new = """from agents.meta_agent.task_gateway import gateway
from agents.meta_agent.task_integrity import run_task_integrity_check, complete_task_record"""

content = content.replace(old, new)

old_invoke = '''    try:
        final_state = meta_agent_graph.invoke(initial_state, config=config)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Graph execution failed: " + str(e))

    report = final_state.get("founder_report")
    if not report:
        raise HTTPException(status_code=500, detail="No report returned from graph.")

    return CreateAgentResponse(
        task_id=report.task_id,
        status=report.status,
        summary=report.summary,
        agent_name=report.agent_name,
        total_tokens_used=report.total_tokens_used,
        errors=report.errors,
        rollback_command=report.rollback_command,
    )'''

new_invoke = '''    integrity_ok, integrity_errors = run_task_integrity_check(task_envelope)
    if not integrity_ok:
        raise HTTPException(status_code=400, detail=" | ".join(integrity_errors))

    try:
        final_state = meta_agent_graph.invoke(initial_state, config=config)
    except Exception as e:
        complete_task_record(task_id, "failed", output_preview=str(e))
        raise HTTPException(status_code=500, detail="Graph execution failed: " + str(e))

    report = final_state.get("founder_report")
    if not report:
        complete_task_record(task_id, "failed", output_preview="No report returned")
        raise HTTPException(status_code=500, detail="No report returned from graph.")

    complete_task_record(
        task_id=task_id,
        status=report.status.lower(),
        tokens_used=report.total_tokens_used,
        output_preview=report.summary,
    )

    return CreateAgentResponse(
        task_id=report.task_id,
        status=report.status,
        summary=report.summary,
        agent_name=report.agent_name,
        total_tokens_used=report.total_tokens_used,
        errors=report.errors,
        rollback_command=report.rollback_command,
    )'''

content = content.replace(old_invoke, new_invoke)

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("api.py updated with task integrity loop")
