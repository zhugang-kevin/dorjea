import time
import httpx
from agents.meta_agent.agent_auditor import audit_all_agents
from agents.meta_agent.registry import get_agent, update_agent_status

API = "http://127.0.0.1:8000"

def regenerate_failing_agents(max_agents=50, min_score=80):
    report = audit_all_agents()
    to_regenerate = [
        r for r in report['results']
        if r['score'] < min_score
    ]
    print("Agents to regenerate: " + str(len(to_regenerate)))
    print("")
    success = 0
    failed = 0
    for item in to_regenerate[:max_agents]:
        name = item['agent']
        agent = get_agent(name)
        if not agent:
            print("SKIP: " + name + " (not found)")
            continue
        mission = agent.get('mission', '')
        department = agent.get('department', 'general')
        if not mission:
            print("SKIP: " + name + " (no mission)")
            continue
        update_agent_status(name, 'archived')
        request = (
            "Create a " + name.replace('_', ' ') +
            " for the " + department + " department. " +
            "Mission: " + mission[:300]
        )
        print("Regenerating: " + name + "...")
        try:
            response = httpx.post(
                API + "/agents/create",
                json={"request": request},
                timeout=120,
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "SUCCESS":
                    print("  OK: " + result.get("agent_name", name) + " | tokens: " + str(result.get("total_tokens_used", 0)))
                    success += 1
                else:
                    errors = result.get("errors", [])
                    already = any("already exists" in str(e) for e in errors)
                    if already:
                        print("  SKIP: " + name + " already exists with new schema")
                        update_agent_status(name, 'active')
                        success += 1
                    else:
                        print("  FAILED: " + str(result.get("summary", "")))
                        update_agent_status(name, 'active')
                        failed += 1
            else:
                print("  HTTP ERROR: " + str(response.status_code))
                update_agent_status(name, 'active')
                failed += 1
        except Exception as e:
            print("  EXCEPTION: " + str(e)[:100])
            update_agent_status(name, 'active')
            failed += 1
        time.sleep(3)
    print("")
    print("Regeneration complete.")
    print("Success: " + str(success))
    print("Failed: " + str(failed))

if __name__ == "__main__":
    regenerate_failing_agents()