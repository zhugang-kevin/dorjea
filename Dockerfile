FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc curl && rm -rf /var/lib/apt/lists/*

COPY requirements.docker.txt .
RUN pip install --no-cache-dir -r requirements.docker.txt

COPY . .

RUN python memory/init_db.py || true

RUN mkdir -p logs agents/specs agents/generated agents/manifests memory/agent_memory logs/reproductions

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

CMD ["python", "start.py"]
