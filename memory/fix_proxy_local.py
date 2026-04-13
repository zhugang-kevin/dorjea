import os

with open("scripts/clear_proxy.ps1", "r", encoding="utf-8") as f:
    content = f.read()

# Add a helper function for local API calls
addition = """
# Helper function for local API calls - always bypasses proxy
function Invoke-LocalAPI {
    param($Uri, $Method = "GET", $Body = $null, $ContentType = "application/json")
    if ($Body) {
        return Invoke-RestMethod -Uri $Uri -Method $Method -Body $Body -ContentType $ContentType -NoProxy
    }
    return Invoke-RestMethod -Uri $Uri -Method $Method -NoProxy
}
Write-Host "Local API helper loaded. Use Invoke-LocalAPI instead of Invoke-RestMethod." -ForegroundColor Cyan
"""

content = content + addition

with open("scripts/clear_proxy.ps1", "w", encoding="utf-8") as f:
    f.write(content)
print("clear_proxy.ps1 updated with Invoke-LocalAPI helper")
