from __future__ import annotations
from typing import Any


def score_output(output, acceptance_criteria, task_instruction):
    if not acceptance_criteria:
        return 1.0, []
    failed = []
    passed = 0
    output_str = str(output).lower()
    for criterion in acceptance_criteria:
        c_lower = criterion.lower()
        if "contains" in c_lower:
            keyword = c_lower.split('contains')[-1].strip().strip()
            if keyword in output_str:
                passed += 1
            else:
                failed.append(criterion)
        elif "length" in c_lower:
            passed += 1
        elif "schema" in c_lower:
            passed += 1
        else:
            passed += 1
    score = passed / max(len(acceptance_criteria), 1)
    return round(score, 3), failed


def needs_retry(score, failed_criteria, retry_count, max_retries=3):
    return score < 0.8 and retry_count < max_retries


def build_correction_prompt(original_instruction, output, failed_criteria, retry_num):
    criteria_list = chr(10).join("- " + c for c in failed_criteria)
    return (
        "[SELF-CORRECTION ATTEMPT " + str(retry_num) + "]" + chr(10) +
        "Your previous output did not meet these criteria:" + chr(10) +
        criteria_list + chr(10) + chr(10) +
        "Original instruction: " + original_instruction + chr(10) +
        "Please produce a corrected output that satisfies all criteria."
    )