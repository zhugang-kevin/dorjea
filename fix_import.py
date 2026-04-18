
with open('agents/meta_agent/nodes.py', encoding='utf-8') as f:
    content = f.read()

# Fix the import name
content = content.replace(
    'from agents.meta_agent.validation_gates import run_all_validation_gates',
    'from agents.meta_agent.validation_gates import run_all_gates as run_all_validation_gates'
)

with open('agents/meta_agent/nodes.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed')
