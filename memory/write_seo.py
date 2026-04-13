content = """
import json
from datetime import datetime


def generate_jsonld(title, description, keywords, author="Dorjea AI Factory"):
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "keywords": ", ".join(keywords) if isinstance(keywords, list) else keywords,
        "author": {
            "@type": "Organization",
            "name": author
        },
        "datePublished": datetime.utcnow().date().isoformat(),
        "dateModified": datetime.utcnow().date().isoformat(),
    }


def generate_meta_tags(title, description, keywords):
    tags = []
    if isinstance(keywords, list):
        kw_str = ", ".join(keywords)
    else:
        kw_str = keywords
    tags.append('<meta name="title" content="' + title + '">')
    tags.append('<meta name="description" content="' + description + '">')
    tags.append('<meta name="keywords" content="' + kw_str + '">')
    tags.append('<meta property="og:title" content="' + title + '">')
    tags.append('<meta property="og:description" content="' + description + '">')
    return chr(10).join(tags)


def generate_faq_schema(faq_pairs):
    entities = []
    for pair in faq_pairs:
        entities.append({
            "@type": "Question",
            "name": pair.get("question", ""),
            "acceptedAnswer": {
                "@type": "Answer",
                "text": pair.get("answer", "")
            }
        })
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": entities
    }


def build_seo_package(title, description, keywords, faq_pairs=None):
    package = {
        "jsonld": generate_jsonld(title, description, keywords),
        "meta_tags": generate_meta_tags(title, description, keywords),
    }
    if faq_pairs:
        package["faq_schema"] = generate_faq_schema(faq_pairs)
    return package
"""

with open("self_seo/seo_generator.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("seo_generator.py created")
