"""
Reliability layer: retry logic, output validation, confidence scoring, fallback strategies.
Applied to all agent task executions and workflow steps.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

MAX_RETRIES = int(os.getenv("TASK_MAX_RETRIES", "3"))
RETRY_DELAY_BASE = float(os.getenv("RETRY_DELAY_BASE", "1.5"))
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE_THRESHOLD", "0.55"))


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def score_output_confidence(output: str, task: str) -> float:
    """
    Rule-based confidence score (0.0–1.0).
    Combines length, structure, relevance signals, and refusal detection.
    """
    if not output or not output.strip():
        return 0.0

    score = 0.5
    text = output.strip()
    words = len(text.split())

    # Length signal
    if words >= 50:
        score += 0.15
    elif words >= 20:
        score += 0.08
    elif words < 5:
        score -= 0.25

    # Structure signal: lists, headers, numbered items
    if re.search(r"(\n[-*•]\s|\n\d+\.\s|#{1,3}\s)", text):
        score += 0.10

    # Refusal / uncertainty patterns
    refusal_patterns = [
        r"\bi (cannot|can't|am unable to|don't know)\b",
        r"\b(sorry|apologies|unfortunately)\b",
        r"\bi (don't|do not) have (access|information|data)\b",
        r"\bas an ai\b",
    ]
    for pat in refusal_patterns:
        if re.search(pat, text, re.IGNORECASE):
            score -= 0.20
            break

    # Task keyword overlap
    task_keywords = set(re.findall(r"\b\w{4,}\b", task.lower()))
    output_keywords = set(re.findall(r"\b\w{4,}\b", text.lower()))
    if task_keywords:
        overlap = len(task_keywords & output_keywords) / len(task_keywords)
        score += overlap * 0.15

    # JSON / structured data bonus
    try:
        json.loads(text)
        score += 0.10
    except (json.JSONDecodeError, ValueError):
        pass

    return max(0.0, min(1.0, round(score, 3)))


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------

def validate_output(output: str, rules: list[dict] | None = None) -> tuple[bool, list[str]]:
    """
    Validate output against a list of rules.
    Each rule: {"type": "min_length"|"max_length"|"contains"|"not_contains"|"regex", "value": ...}
    Returns (passed, list_of_failures).
    """
    if rules is None:
        return True, []

    failures: list[str] = []
    for rule in rules:
        rtype = rule.get("type", "")
        value = rule.get("value")

        if rtype == "min_length":
            if len(output) < int(value):
                failures.append(f"Output too short (min {value} chars)")
        elif rtype == "max_length":
            if len(output) > int(value):
                failures.append(f"Output too long (max {value} chars)")
        elif rtype == "contains":
            if str(value).lower() not in output.lower():
                failures.append(f"Output missing required content: '{value}'")
        elif rtype == "not_contains":
            if str(value).lower() in output.lower():
                failures.append(f"Output contains forbidden content: '{value}'")
        elif rtype == "regex":
            if not re.search(str(value), output, re.IGNORECASE | re.DOTALL):
                failures.append(f"Output does not match pattern: '{value}'")

    return len(failures) == 0, failures


# ---------------------------------------------------------------------------
# Retry with exponential backoff
# ---------------------------------------------------------------------------

def with_retry(
    fn: Callable[[], dict[str, Any]],
    max_retries: int = MAX_RETRIES,
    delay_base: float = RETRY_DELAY_BASE,
    task_description: str = "",
    validation_rules: list[dict] | None = None,
    confidence_threshold: float = MIN_CONFIDENCE,
) -> dict[str, Any]:
    """
    Execute fn() with retry + exponential backoff.
    Retries on: exception, FAILED status, low confidence, validation failure.
    Returns the best result or the last failure.
    """
    last_result: dict[str, Any] = {}
    best_result: dict[str, Any] = {}
    best_confidence = -1.0

    for attempt in range(1, max_retries + 1):
        try:
            result = fn()
        except Exception as exc:
            last_result = {
                "status": "FAILED",
                "error": str(exc),
                "attempt": attempt,
                "output": "",
            }
            logger.warning("Attempt %d/%d failed with exception: %s", attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(delay_base ** (attempt - 1))
            continue

        output = str(result.get("output", "") or "")
        confidence = score_output_confidence(output, task_description)
        result.setdefault("reliability", {})
        result["reliability"]["confidence"] = confidence
        result["reliability"]["attempt"] = attempt

        valid, validation_failures = validate_output(output, validation_rules)
        result["reliability"]["validation_passed"] = valid
        result["reliability"]["validation_failures"] = validation_failures

        if result.get("status") == "SUCCESS" and confidence >= confidence_threshold and valid:
            result["reliability"]["retries_used"] = attempt - 1
            return result

        # Track best result so far
        if confidence > best_confidence:
            best_confidence = confidence
            best_result = result

        last_result = result
        logger.info(
            "Attempt %d/%d: status=%s confidence=%.2f valid=%s",
            attempt, max_retries, result.get("status"), confidence, valid,
        )

        if attempt < max_retries:
            time.sleep(delay_base ** (attempt - 1))

    # Return best result we got, annotated
    final = best_result or last_result
    final.setdefault("reliability", {})
    final["reliability"]["retries_used"] = max_retries - 1
    final["reliability"]["exhausted"] = True
    return final


# ---------------------------------------------------------------------------
# Fallback strategy
# ---------------------------------------------------------------------------

def with_fallback(
    primary_fn: Callable[[], dict[str, Any]],
    fallback_fn: Callable[[], dict[str, Any]] | None,
    task_description: str = "",
    confidence_threshold: float = MIN_CONFIDENCE,
) -> dict[str, Any]:
    """
    Try primary_fn first; if it fails or confidence is too low, try fallback_fn.
    """
    result = with_retry(primary_fn, task_description=task_description,
                        confidence_threshold=confidence_threshold)

    confidence = result.get("reliability", {}).get("confidence", 0.0)
    if result.get("status") == "SUCCESS" and confidence >= confidence_threshold:
        return result

    if fallback_fn is None:
        result.setdefault("reliability", {})
        result["reliability"]["fallback_used"] = False
        return result

    logger.info("Primary failed (confidence=%.2f), trying fallback", confidence)
    fallback_result = with_retry(fallback_fn, task_description=task_description,
                                 confidence_threshold=confidence_threshold)
    fallback_result.setdefault("reliability", {})
    fallback_result["reliability"]["fallback_used"] = True
    return fallback_result
