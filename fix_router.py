
with open('agents/runtime/model_router.py', encoding='utf-8') as f:
    content = f.read()

# Fix: always continue to next provider on any error
old = '''            if result['error']:
                last_error = result['error']
                write_audit_entry(AuditEntry(agent_id='model_router', task_id=task_id, action='PROVIDER_FAILED', details={'provider': provider, 'error': str(last_error)[:200]}, success=False))
                if _is_connection_error(last_error) or _is_auth_error(last_error):
                    continue
                return result'''

new = '''            if result['error']:
                last_error = result['error']
                write_audit_entry(AuditEntry(agent_id='model_router', task_id=task_id, action='PROVIDER_FAILED', details={'provider': provider, 'error': str(last_error)[:200]}, success=False))
                continue'''

if old in content:
    content = content.replace(old, new)
    with open('agents/runtime/model_router.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Router fixed - now always falls back on any error')
else:
    print('Pattern not found - checking content...')
    idx = content.find('if result')
    print(content[idx:idx+300])
