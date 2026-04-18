
with open('agents/meta_agent/api.py', encoding='utf-8') as f:
    content = f.read()

if 'tools_router' not in content:
    content = content.replace(
        'from agents.meta_agent.templates import router as templates_router',
        'from agents.meta_agent.templates import router as templates_router\nfrom agents.meta_agent.tools import router as tools_router'
    )
    content = content.replace(
        'app.include_router(templates_router)',
        'app.include_router(templates_router)\napp.include_router(tools_router)'
    )
    with open('agents/meta_agent/api.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Tools router registered')
else:
    print('Already registered')
