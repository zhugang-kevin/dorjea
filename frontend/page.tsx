"use client";
import { useState, useEffect } from "react";
import axios from "axios";

const API = "http://127.0.0.1:8000";

const card = (label: string, value: any, color = "#38bdf8") => (
  <div key={label} style={{ background: "#1e293b", borderRadius: 12, padding: "20px 24px", flex: 1 }}>
    <div style={{ fontSize: 13, color: "#64748b", marginBottom: 8 }}>{label}</div>
    <div style={{ fontSize: 32, fontWeight: 700, color }}>{value ?? "—"}</div>
  </div>
);

export default function Dashboard() {
  const [health, setHealth] = useState<any>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [request, setRequest] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("dashboard");
  const [runAgent, setRunAgent] = useState("");
  const [runTask, setRunTask] = useState("");
  const [runResult, setRunResult] = useState<any>(null);
  const [runLoading, setRunLoading] = useState(false);

  const load = async () => {
    try { setHealth((await axios.get(`${API}/health`)).data); } catch {}
    try { setAgents((await axios.get(`${API}/agents`)).data.agents || []); } catch {}
    try { setMetrics((await axios.get(`${API}/metrics`)).data); } catch {}
  };

  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, []);

  const createAgent = async () => {
    if (!request.trim()) return;
    setLoading(true); setResult(null);
    try { setResult((await axios.post(`${API}/agents/create`, { request })).data); load(); }
    catch (e: any) { setResult({ status: "FAILED", summary: e.message }); }
    setLoading(false);
  };

  const executeTask = async () => {
    if (!runAgent || !runTask.trim()) return;
    setRunLoading(true); setRunResult(null);
    try { setRunResult((await axios.post(`${API}/agents/${runAgent}/run`, { task: runTask })).data); }
    catch (e: any) { setRunResult({ status: "FAILED", error: e.message }); }
    setRunLoading(false);
  };

  const tabs = ["dashboard", "create", "agents", "run"];

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <div style={{ width: 220, background: "#0f172a", borderRight: "1px solid #1e293b", padding: "24px 16px", flexShrink: 0 }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: "#38bdf8", marginBottom: 8 }}>Dorjea AI Factory</div>
        <div style={{ fontSize: 12, color: health?.status === "healthy" ? "#4ade80" : "#f87171", marginBottom: 32 }}>
          ● {health?.status || "connecting"}
        </div>
        {tabs.map(t => (
          <div key={t} onClick={() => setTab(t)} style={{
            padding: "10px 16px", borderRadius: 8, cursor: "pointer", marginBottom: 4, fontSize: 14, fontWeight: 500,
            background: tab === t ? "#1e293b" : "transparent", color: tab === t ? "#38bdf8" : "#64748b"
          }}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </div>
        ))}
        <div style={{ marginTop: "auto", paddingTop: 32, fontSize: 12, color: "#334155" }}>
          <div>Agents: {agents.length}</div>
          <div>Tokens today: {metrics?.daily_tokens_used?.toLocaleString() || 0}</div>
          <div>Budget: {metrics?.daily_budget ? Math.round((metrics.daily_tokens_used / metrics.daily_budget) * 100) : 0}%</div>
        </div>
      </div>

      <div style={{ flex: 1, padding: 32, overflowY: "auto" }}>

        {tab === "dashboard" && (
          <>
            <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 24, color: "#f1f5f9" }}>System Overview</h2>
            <div style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
              {card("CPU", health?.system?.cpu_percent + "%")}
              {card("Memory", health?.system?.memory_percent + "%")}
              {card("Disk Free", health?.system?.disk_free_gb + " GB")}
              {card("Health Score", health?.drift?.health_score, health?.drift?.health_score > 0.8 ? "#4ade80" : "#f87171")}
            </div>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              {card("Daily Tokens", metrics?.daily_tokens_used?.toLocaleString())}
              {card("Budget Remaining", metrics?.budget_remaining?.toLocaleString())}
              {card("Active Agents", agents.filter(a => a.status === "active").length, "#a78bfa")}
              {card("Drift Status", health?.drift?.status, health?.drift?.drift_detected ? "#f87171" : "#4ade80")}
            </div>
            {health?.alerts?.length > 0 && (
              <div style={{ marginTop: 24, padding: 16, background: "#7f1d1d", borderRadius: 12 }}>
                <strong>Alerts:</strong> {health.alerts.join(" | ")}
              </div>
            )}
          </>
        )}

        {tab === "create" && (
          <>
            <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 24, color: "#f1f5f9" }}>Create New Agent</h2>
            <div style={{ background: "#1e293b", borderRadius: 12, padding: 24 }}>
              <textarea value={request} onChange={e => setRequest(e.target.value)}
                placeholder="Describe the agent you want to create in plain English. Example: Create a research agent that finds and summarizes market trends."
                style={{ width: "100%", height: 140, background: "#0f172a", color: "#e2e8f0", border: "1px solid #334155",
                  borderRadius: 8, padding: 12, fontSize: 14, resize: "vertical", boxSizing: "border-box" }} />
              <button onClick={createAgent} disabled={loading}
                style={{ marginTop: 12, padding: "12px 28px", background: loading ? "#334155" : "#0ea5e9",
                  color: "#fff", border: "none", borderRadius: 8, fontWeight: 600, fontSize: 15, cursor: loading ? "not-allowed" : "pointer" }}>
                {loading ? "Creating agent..." : "Create Agent"}
              </button>
              {result && (
                <div style={{ marginTop: 20, padding: 20, background: result.status === "SUCCESS" ? "#14532d" : "#7f1d1d", borderRadius: 10 }}>
                  <div style={{ fontWeight: 700, fontSize: 16 }}>{result.status}: {result.agent_name}</div>
                  <div style={{ fontSize: 14, marginTop: 6, color: "#94a3b8" }}>{result.summary}</div>
                  {result.total_tokens_used && <div style={{ fontSize: 13, marginTop: 4, color: "#64748b" }}>Tokens used: {result.total_tokens_used?.toLocaleString()}</div>}
                  {result.errors?.length > 0 && <div style={{ fontSize: 13, color: "#fca5a5", marginTop: 4 }}>{result.errors.join(", ")}</div>}
                </div>
              )}
            </div>
          </>
        )}

        {tab === "agents" && (
          <>
            <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 24, color: "#f1f5f9" }}>Registered Agents ({agents.length})</h2>
            {agents.length === 0 && <div style={{ color: "#64748b" }}>No agents registered yet. Create one in the Create tab.</div>}
            {agents.map(agent => (
              <div key={agent.id} style={{ background: "#1e293b", borderRadius: 10, padding: 20, marginBottom: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <span style={{ fontWeight: 700, fontSize: 16, color: "#38bdf8" }}>{agent.name}</span>
                  <div style={{ display: "flex", gap: 8 }}>
                    <span style={{ fontSize: 12, padding: "3px 10px", background: "#166534", borderRadius: 12, color: "#4ade80" }}>{agent.status}</span>
                    <span style={{ fontSize: 12, padding: "3px 10px", background: "#1e3a5f", borderRadius: 12, color: "#7dd3fc" }}>v{agent.version}</span>
                  </div>
                </div>
                <div style={{ fontSize: 13, color: "#94a3b8", marginBottom: 8 }}>{agent.mission?.substring(0, 180)}...</div>
                <div style={{ fontSize: 12, color: "#475569" }}>Tools: {agent.allowed_tools} | Budget: {agent.token_budget?.toLocaleString()} tokens</div>
              </div>
            ))}
          </>
        )}

        {tab === "run" && (
          <>
            <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 24, color: "#f1f5f9" }}>Run Agent Task</h2>
            <div style={{ background: "#1e293b", borderRadius: 12, padding: 24 }}>
              <select value={runAgent} onChange={e => setRunAgent(e.target.value)}
                style={{ width: "100%", padding: "10px 12px", background: "#0f172a", color: "#e2e8f0",
                  border: "1px solid #334155", borderRadius: 8, fontSize: 14, marginBottom: 12 }}>
                <option value="">Select an agent...</option>
                {agents.filter(a => a.status === "active").map(a => (
                  <option key={a.id} value={a.name}>{a.name}</option>
                ))}
              </select>
              <textarea value={runTask} onChange={e => setRunTask(e.target.value)}
                placeholder="Describe the task for this agent..."
                style={{ width: "100%", height: 120, background: "#0f172a", color: "#e2e8f0", border: "1px solid #334155",
                  borderRadius: 8, padding: 12, fontSize: 14, resize: "vertical", boxSizing: "border-box" }} />
              <button onClick={executeTask} disabled={runLoading || !runAgent}
                style={{ marginTop: 12, padding: "12px 28px", background: runLoading || !runAgent ? "#334155" : "#7c3aed",
                  color: "#fff", border: "none", borderRadius: 8, fontWeight: 600, fontSize: 15, cursor: "pointer" }}>
                {runLoading ? "Running..." : "Run Task"}
              </button>
              {runResult && (
                <div style={{ marginTop: 20, padding: 20, background: "#0f172a", borderRadius: 10, border: "1px solid #334155" }}>
                  <div style={{ fontWeight: 700, marginBottom: 8, color: runResult.status === "SUCCESS" ? "#4ade80" : "#f87171" }}>
                    {runResult.status}
                  </div>
                  <div style={{ fontSize: 14, color: "#e2e8f0", whiteSpace: "pre-wrap", lineHeight: 1.6 }}>
                    {runResult.output || runResult.error}
                  </div>
                  {runResult.tokens_used && <div style={{ fontSize: 12, color: "#64748b", marginTop: 8 }}>Tokens: {runResult.tokens_used}</div>}
                </div>
              )}
            </div>
          </>
        )}

      </div>
    </div>
  );
}
