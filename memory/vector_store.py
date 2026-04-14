import json, numpy as np
from pathlib import Path
from datetime import datetime

VECTOR_STORE = Path('memory/embeddings/vector_store.jsonl')
DIMENSION = 384

def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))

def store_embedding(doc_id, text, embedding, metadata=None):
    VECTOR_STORE.parent.mkdir(parents=True, exist_ok=True)
    record = {'doc_id': doc_id, 'text': text[:500], 'embedding': embedding, 'metadata': metadata or {}, 'stored_at': datetime.utcnow().isoformat()}
    with open(VECTOR_STORE, 'a', encoding='utf-8') as f: f.write(json.dumps(record) + chr(10))
    return True

def load_all_embeddings():
    if not VECTOR_STORE.exists(): return []
    records = []
    try:
        with open(VECTOR_STORE, encoding='utf-8') as f:
            for line in f:
                if line.strip(): records.append(json.loads(line.strip()))
    except Exception: pass
    return records

def search_similar(query_embedding, top_k=5, threshold=0.5):
    scored = [{'doc_id': r['doc_id'], 'text': r['text'], 'similarity': round(cosine_similarity(query_embedding, r['embedding']), 4), 'metadata': r.get('metadata', {})} for r in load_all_embeddings()]
    return sorted([s for s in scored if s['similarity'] >= threshold], key=lambda x: x['similarity'], reverse=True)[:top_k]

def get_vector_stats():
    records = load_all_embeddings()
    return {'total_embeddings': len(records), 'store_path': str(VECTOR_STORE), 'dimension': DIMENSION, 'backend': 'numpy_cosine_similarity', 'note': 'pgvector pending PostgreSQL 18 Windows support'}
