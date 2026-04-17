with open("app/affiliate/page.tsx", "r", encoding="utf-8") as f:
    content = f.read()

old = """              <div style={{marginTop:12,fontSize:13,color:c.muted}}>
                Affiliate Code: <span style={{color:c.primary,fontWeight:700,fontFamily:"monospace"}}>{stats.affiliate.code}</span>
              </div>"""

new = """              <div style={{marginTop:12,display:"flex",alignItems:"center",gap:12,flexWrap:"wrap"}}>
                <div style={{fontSize:13,color:c.muted}}>
                  Affiliate Code: <span style={{color:c.primary,fontWeight:700,fontFamily:"monospace"}}>{stats.affiliate.code}</span>
                </div>
                <a href={stats.affiliate.referral_link} target="_blank" rel="noopener noreferrer"
                  style={{padding:"8px 20px",background:"rgba(56,189,248,0.15)",
                    border:"1px solid "+c.primary,borderRadius:8,color:c.primary,
                    textDecoration:"none",fontSize:13,fontWeight:700,display:"flex",
                    alignItems:"center",gap:6}}>
                  🔗 Open Referral Link
                </a>
                <a href={"https://dorjea.com/login?ref="+stats.affiliate.code} target="_blank" rel="noopener noreferrer"
                  style={{padding:"8px 20px",background:c.primary,
                    borderRadius:8,color:"#fff",
                    textDecoration:"none",fontSize:13,fontWeight:700,display:"flex",
                    alignItems:"center",gap:6}}>
                  🚀 Share & Invite
                </a>
              </div>"""

if old in content:
    content = content.replace(old, new)
    with open("app/affiliate/page.tsx", "w", encoding="utf-8") as f:
        f.write(content)
    print("Affiliate CTA buttons added")
else:
    print("Pattern not found")
