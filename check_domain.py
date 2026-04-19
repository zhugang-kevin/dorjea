
import os

results = []
for root, dirs, files in os.walk('agents'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, encoding='utf-8') as f:
                content = f.read()
            if 'dorjea.ai' in content:
                results.append((path, content.count('dorjea.ai')))

for path, count in results:
    print(path, ':', count, 'occurrences')

print('Total files with dorjea.ai:', len(results))
