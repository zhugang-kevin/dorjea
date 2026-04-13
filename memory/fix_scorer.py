with open("self_correction/quality_scorer.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

lines[13] = "            keyword = c_lower.split('contains')[-1].strip().strip()\n"

with open("self_correction/quality_scorer.py", "w", encoding="utf-8") as f:
    f.writelines(lines)
print("fixed")
