with open("requirements.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Remove Windows-only packages that cannot install in Linux containers
windows_only = ["pywin32", "pywinpty", "colorama"]
filtered = [l for l in lines if not any(pkg in l.lower() for pkg in windows_only)]

with open("requirements.txt", "w", encoding="utf-8") as f:
    f.writelines(filtered)

print("requirements.txt cleaned — removed Windows-only packages")
print("Remaining packages:", len(filtered))
