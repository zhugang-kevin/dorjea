import os
from agents.runtime.ai_clients import ClaudeClient, OpenAIClient, DeepSeekClient
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry

PROVIDER_ORDER = ['claude', 'openai', 'deepseek']

def _is_connection_error(error):
    if not error: return False
    e = str(error).lower()
    return any(k in e for k in ['connection', 'timeout', 'network', 'proxy', 'unreachable', 'refused', 'reset', 'ssl'])

def _is_auth_error(error):
    if not error: return False
    e = str(error).lower()
    return any(k in e for k in ['401', 'authentication', 'invalid api key', 'unauthorized'])

def call_with_fallback(prompt, system='', max_tokens=2000, task_id='routing'):
    clients = {
        'claude': ClaudeClient(),
        'openai': OpenAIClient(),
        'deepseek': DeepSeekClient(),
    }
    last_error = None
    for provider in PROVIDER_ORDER:
        client = clients[provider]
        try:
            result = client.call(prompt, system=system, max_tokens=max_tokens)
            if result['error']:
                last_error = result['error']
                write_audit_entry(AuditEntry(agent_id='model_router', task_id=task_id, action='PROVIDER_FAILED', details={'provider': provider, 'error': str(last_error)[:200]}, success=False))
                if _is_connection_error(last_error) or _is_auth_error(last_error):
                    continue
                return result
            write_audit_entry(AuditEntry(agent_id='model_router', task_id=task_id, action='PROVIDER_SUCCESS', details={'provider': provider, 'tokens': result['total_tokens']}, success=True))
            result['provider'] = provider
            return result
        except Exception as e:
            last_error = str(e)
            write_audit_entry(AuditEntry(agent_id='model_router', task_id=task_id, action='PROVIDER_EXCEPTION', details={'provider': provider, 'error': str(e)[:200]}, success=False))
            continue
    return {'text': '', 'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0, 'error': 'All providers failed. Last error: ' + str(last_error), 'provider': 'none'}

model_router = type('ModelRouter', (), {'call': staticmethod(call_with_fallback)})()
