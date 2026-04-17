with open("agents/meta_agent/affiliate.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '"referral_link": "https://dorjea.ai/login?ref=" + code,'
new = '"referral_link": "https://dorjea.com/login?ref=" + code,'

content = content.replace(old, new)

with open("agents/meta_agent/affiliate.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Affiliate referral link fixed to dorjea.com")
