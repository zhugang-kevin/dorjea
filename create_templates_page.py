import os
os.makedirs('app/templates', exist_ok=True)
BKT = chr(96)
DOLLAR = chr(36)

code = '''
"use client";
import { useState, useEffect } from "react";
import axios from "axios";
import { useApp, ThemeLangBar } from "../../lib/context";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const CATEGORY_COLORS: Record<string,string> = {
  Sales: "#16a34a",
  Marketing: "#7c3aed",
  Research: "#0284c7",
  Operations: "#ea580c",
  Engineering: "#2563eb",
  Strategy: "#dc2626",
  Finance: "#0891b2",
  "Customer Success": "#059669",
};

export default function TemplatesPage() {
  const { c } = useApp();
  const [templates, setTemplates] = useState<any[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("All");
  const [search, setSearch] = useState("");
  const [installing, setInstalling] = useState<string|null>(null);
  const [installed, setInstalled] = useState<Set<string>>(new Set());
  const [preview, setPreview] = useState<any|null>(null);
  const [user, setUser] = useState<any>(null);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(()=>{
    const u = localStorage.getItem("dorjea_user");
    if (!u) { window.location.href="/login"; return; }
    setUser(JSON.parse(u));
    loadTemplates();
  },[]);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const res = await axios.get(''' + BKT + DOLLAR + '''{API}/templates/list''' + BKT + ''');
      setTemplates(res.data.templates || []);
      const cats = ["All", ...Array.from(new Set((res.data.templates||[]).map((t:any)=>t.category))) as string[]];
      setCategories(cats);
    } catch {}
    setLoading(false);
  };

  const loadPreview = async (template_id: string) => {
    try {
      const res = await axios.get(''' + BKT + DOLLAR + '''{API}/templates/get/''' + DOLLAR + '''{template_id}''' + BKT + ''');
      setPreview(res.data);
    } catch {}
  };

  const installTemplate = async (template_id: string, name: string) => {
    if (!user) return;
    setInstalling(template_id); setError("");
    try {
      await axios.post(''' + BKT + DOLLAR + '''{API}/templates/install''' + BKT + ''', {
        template_id,
        user_email: user.email,
        custom_name: "",
      });
      setInstalled(prev => new Set([...prev, template_id]));
      setSuccess(''' + BKT + DOLLAR + '''{name} installed successfully! Find it in your Dashboard agents list.''' + BKT + ''');
      if (preview?.template_id === template_id) setPreview(null);
      setTimeout(()=>setSuccess(""), 4000);
    } catch(e:any) {
      setError(e.response?.data?.detail || "Failed to install template");
    }
    setInstalling(null);
  };

  const filtered = templates.filter(t => {
    const matchCat = selected === "All" || t.category === selected;
    const matchSearch = !search || t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.description.toLowerCase().includes(search.toLowerCase());
    return matchCat && matchSearch;
  });

  const grouped: Record<string, any[]> = {};
  filtered.forEach(t => {
    if (!grouped[t.category]) grouped[t.category] = [];
    grouped[t.category].push(t);
  });

  return (
    <div style={{minHeight:"100vh",background:c.bg,color:c.text,fontFamily:"system-ui,-apple-system,sans-serif"}}>
      <div style={{background:c.card,borderBottom:"1px solid "+c.border,padding:"16px 32px",
        display:"flex",alignItems:"center",justifyContent:"space-between"}}>
        <div style={{display:"flex",alignItems:"center",gap:16}}>
          <a href="/dashboard" style={{color:c.muted,textDecoration:"none",fontSize:14}}>← Dashboard</a>
          <span style={{color:c.border}}>|</span>
          <span style={{fontSize:20,fontWeight:800,color:c.primary}}>🤖 Agent Templates</span>
          <span style={{fontSize:12,padding:"3px 10px",background:c.primary+"22",color:c.primary,
            borderRadius:12,fontWeight:700}}>{templates.length} templates</span>
        </div>
        <ThemeLangBar />
      </div>

      <div style={{maxWidth:1300,margin:"0 auto",padding:32}}>

        <div style={{background:"linear-gradient(135deg,"+c.primary+"18,"+c.primary+"05)",
          borderRadius:16,padding:28,border:"1.5px solid "+c.primary+"33",marginBottom:32}}>
          <h2 style={{fontSize:24,fontWeight:800,margin:"0 0 8px",color:c.text}}>
            Install a Professional Agent in One Click
          </h2>
          <p style={{color:c.muted,fontSize:15,margin:"0 0 16px",lineHeight:1.7}}>
            Each template is designed by senior professionals with complete 16-layer DNA specifications.
            Grade A quality guaranteed. Install instantly — your agent is ready to run tasks immediately.
          </p>
          <div style={{display:"flex",gap:16,flexWrap:"wrap"}}>
            {["⚡ Instant setup","🎯 Grade A quality","📋 16-layer DNA","🔧 Fully customizable"].map((f,i)=>(
              <div key={i} style={{padding:"8px 16px",background:c.card,borderRadius:20,
                fontSize:13,color:c.text,border:"1px solid "+c.border}}>{f}</div>
            ))}
          </div>
        </div>

        {success&&<div style={{padding:16,background:"#f0fdf4",borderRadius:10,color:"#16a34a",
          fontSize:14,marginBottom:20,border:"1px solid #86efac"}}>{success}</div>}
        {error&&<div style={{padding:14,background:"#fef2f2",borderRadius:10,color:"#dc2626",
          fontSize:14,marginBottom:20,border:"1px solid #fecaca"}}>{error}</div>}

        <div style={{display:"flex",gap:12,marginBottom:28,flexWrap:"wrap"}}>
          <input value={search} onChange={e=>setSearch(e.target.value)}
            placeholder="Search templates..."
            style={{padding:"10px 16px",background:c.card,color:c.text,
              border:"1.5px solid "+c.border,borderRadius:10,fontSize:14,
              fontFamily:"system-ui",outline:"none",width:280}} />
          <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
            {categories.map(cat=>(
              <button key={cat} onClick={()=>setSelected(cat)}
                style={{padding:"10px 18px",borderRadius:10,border:"none",cursor:"pointer",
                  fontSize:13,fontWeight:600,transition:"all 0.15s",
                  background:selected===cat?(CATEGORY_COLORS[cat]||c.primary):"transparent",
                  color:selected===cat?"#fff":c.muted}}>
                {cat}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div style={{textAlign:"center",padding:60,color:c.muted,fontSize:16}}>
            Loading templates...
          </div>
        ) : (
          <div>
            {Object.entries(grouped).map(([category, temps])=>(
              <div key={category} style={{marginBottom:40}}>
                <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:16}}>
                  <div style={{width:4,height:24,background:CATEGORY_COLORS[category]||c.primary,borderRadius:2}} />
                  <h3 style={{fontSize:18,fontWeight:800,color:c.text,margin:0}}>{category}</h3>
                  <span style={{fontSize:13,color:c.muted}}>{temps.length} templates</span>
                </div>
                <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:16}}>
                  {temps.map(t=>(
                    <div key={t.template_id}
                      style={{background:c.card,borderRadius:14,border:"1.5px solid "+c.border,
                        overflow:"hidden",transition:"all 0.2s",cursor:"pointer"}}
                      onMouseEnter={e=>{(e.currentTarget as HTMLElement).style.borderColor=t.color;(e.currentTarget as HTMLElement).style.transform="translateY(-2px)";(e.currentTarget as HTMLElement).style.boxShadow="0 8px 24px rgba(0,0,0,0.1)";}}
                      onMouseLeave={e=>{(e.currentTarget as HTMLElement).style.borderColor=c.border;(e.currentTarget as HTMLElement).style.transform="none";(e.currentTarget as HTMLElement).style.boxShadow="none";}}>
                      <div style={{padding:20}}>
                        <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:12}}>
                          <div style={{fontSize:32}}>{t.icon}</div>
                          <span style={{fontSize:11,padding:"3px 8px",borderRadius:10,fontWeight:700,
                            background:t.color+"22",color:t.color}}>{t.category}</span>
                        </div>
                        <div style={{fontSize:14,fontWeight:700,color:c.text,marginBottom:6}}>{t.name}</div>
                        <div style={{fontSize:12,color:c.muted,lineHeight:1.5,marginBottom:12,
                          display:"-webkit-box",WebkitLineClamp:2,WebkitBoxOrient:"vertical",overflow:"hidden"}}>
                          {t.description}
                        </div>
                        <div style={{display:"flex",flexWrap:"wrap",gap:4,marginBottom:12}}>
                          {(t.use_cases||[]).slice(0,2).map((uc:string,i:number)=>(
                            <span key={i} style={{fontSize:10,padding:"2px 7px",background:c.bg,
                              borderRadius:8,color:c.muted,border:"1px solid "+c.border}}>{uc}</span>
                          ))}
                        </div>
                        <div style={{display:"flex",gap:8}}>
                          <button
                            onClick={()=>loadPreview(t.template_id)}
                            style={{flex:1,padding:"8px",background:"transparent",
                              border:"1px solid "+c.border,borderRadius:8,
                              color:c.muted,cursor:"pointer",fontSize:12,fontWeight:600}}>
                            Preview
                          </button>
                          <button
                            onClick={()=>installTemplate(t.template_id, t.name)}
                            disabled={installing===t.template_id||installed.has(t.template_id)}
                            style={{flex:1,padding:"8px",
                              background:installed.has(t.template_id)?"#16a34a":t.color,
                              border:"none",borderRadius:8,color:"#fff",
                              cursor:installed.has(t.template_id)?"default":"pointer",
                              fontSize:12,fontWeight:700,opacity:installing===t.template_id?0.7:1}}>
                            {installing===t.template_id?"Installing...":installed.has(t.template_id)?"✓ Installed":"Install"}
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {preview&&(
        <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.6)",zIndex:1000,
          display:"flex",alignItems:"center",justifyContent:"center",padding:24,overflowY:"auto"}}>
          <div style={{background:c.card,borderRadius:20,padding:36,maxWidth:680,width:"100%",
            border:"1.5px solid "+c.border,maxHeight:"90vh",overflowY:"auto"}}>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:24}}>
              <div style={{display:"flex",alignItems:"center",gap:16}}>
                <span style={{fontSize:48}}>{preview.icon}</span>
                <div>
                  <h2 style={{fontSize:22,fontWeight:800,margin:"0 0 4px",color:c.text}}>{preview.name}</h2>
                  <span style={{fontSize:13,padding:"3px 10px",borderRadius:12,fontWeight:700,
                    background:(preview.color||c.primary)+"22",color:preview.color||c.primary}}>
                    {preview.category}
                  </span>
                </div>
              </div>
              <button onClick={()=>setPreview(null)}
                style={{background:"transparent",border:"none",fontSize:24,cursor:"pointer",color:c.muted}}>✕</button>
            </div>

            <p style={{color:c.muted,fontSize:15,lineHeight:1.7,marginBottom:24}}>{preview.description}</p>

            {[
              ["Mission", preview.spec?.mission],
              ["Knowledge", preview.spec?.knowledge],
              ["Core Competencies", preview.spec?.competencies],
              ["Decision Rules", preview.spec?.decisions],
              ["Execution Workflow", preview.spec?.workflow],
              ["Quality Standards", preview.spec?.quality],
              ["Boundaries", preview.spec?.boundaries],
            ].map(([label, value])=>(
              <div key={label as string} style={{marginBottom:16}}>
                <div style={{fontSize:12,fontWeight:700,color:preview.color||c.primary,
                  letterSpacing:1,marginBottom:6}}>{label as string}</div>
                <div style={{fontSize:13,color:c.muted,lineHeight:1.7,padding:"12px 16px",
                  background:c.bg,borderRadius:8,border:"1px solid "+c.border}}>
                  {String(value||"")}
                </div>
              </div>
            ))}

            <div style={{display:"flex",gap:12,marginTop:24}}>
              <button
                onClick={()=>installTemplate(preview.template_id, preview.name)}
                disabled={installing===preview.template_id||installed.has(preview.template_id)}
                style={{flex:1,padding:"14px",background:installed.has(preview.template_id)?"#16a34a":preview.color||c.primary,
                  color:"#fff",border:"none",borderRadius:10,fontWeight:700,fontSize:15,cursor:"pointer"}}>
                {installing===preview.template_id?"Installing...":installed.has(preview.template_id)?"✓ Installed":"Install This Agent"}
              </button>
              <button onClick={()=>setPreview(null)}
                style={{padding:"14px 20px",background:"transparent",color:c.muted,
                  border:"1.5px solid "+c.border,borderRadius:10,cursor:"pointer"}}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
'''

with open('app/templates/page.tsx', 'w', encoding='utf-8') as f:
    f.write(code.strip())
print('Templates page created')
