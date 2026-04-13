content = """
from datetime import datetime


def generate_llm_context_block(title, summary, key_points, source="Dorjea AI Factory"):
    points = chr(10).join("- " + p for p in key_points)
    return (
        "## " + title + chr(10) +
        "Source: " + source + chr(10) +
        "Date: " + datetime.utcnow().date().isoformat() + chr(10) +
        chr(10) +
        "Summary: " + summary + chr(10) +
        chr(10) +
        "Key Points:" + chr(10) +
        points
    )


def generate_qa_pairs(topic, facts):
    pairs = []
    for fact in facts:
        pairs.append({
            "question": "What is the key information about " + topic + " regarding: " + fact[:50] + "?",
            "answer": fact
        })
    return pairs


def generate_aieo_package(title, summary, key_points, facts=None):
    package = {
        "llm_context": generate_llm_context_block(title, summary, key_points),
        "qa_pairs": generate_qa_pairs(title, facts or key_points),
        "structured_summary": {
            "title": title,
            "summary": summary,
            "key_points": key_points,
            "generated_at": datetime.utcnow().isoformat(),
            "source": "Dorjea AI Factory",
        }
    }
    return package
"""

with open("self_aieo/aieo_generator.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("aieo_generator.py created")
