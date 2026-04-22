class ModelRouter:
    def route(self, task_type):
        if task_type == 'planning':
            return 'claude'
        elif task_type == 'coding':
            return 'codex'
        else:
            return 'claude'
