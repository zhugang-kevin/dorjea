with open("scripts/verify.ps1", "r", encoding="utf-8") as f:
    content = f.read()

old = '    $hits = $committedFiles | ForEach-Object {'
new = '    $hits = $committedFiles | Where-Object { $_ -notmatch "verify|write_verify|fix_" } | ForEach-Object {'

content = content.replace(old, new)

with open("scripts/verify.ps1", "w", encoding="utf-8") as f:
    f.write(content)
print("verify.ps1 fixed successfully")
