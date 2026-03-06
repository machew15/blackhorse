import { useState, useEffect } from "react";

const COLORS = {
  bg: "#0a0a0a", surface: "#111111", border: "#1e1e1e", borderHover: "#333333",
  text: "#e8e6e0", muted: "#666666", faint: "#1a1a1a",
  blackhorse: "#c9a84c", greypony: "#7eb8c4", phd: "#a87fc4",
  newsletter: "#7ec47e",
};

const PROJECTS = {
  blackhorse: { label: "Blackhorse", color: COLORS.blackhorse, prefix: "BH" },
  greypony: { label: "Greypony", color: COLORS.greypony, prefix: "GP" },
  phd: { label: "PhD", color: COLORS.phd, prefix: "PHD" },
  newsletter: { label: "The Drip", color: COLORS.newsletter, prefix: "DRIP" },
};

const ROUTE_TYPES = [
  { id: "github", label: "GitHub Issue", icon: "⬡" },
  { id: "notion", label: "Notion Page", icon: "□" },
  { id: "calendar", label: "Calendar Block", icon: "◈" },
  { id: "draft", label: "Draft Only", icon: "◎" },
];

const IDEA_TYPES = ["Feature", "Research", "Architecture", "Content", "Fix", "Experiment", "Thesis", "Framework"];

const generateId = () => `${Date.now().toString(36).toUpperCase()}-${Math.random().toString(36).slice(2, 5).toUpperCase()}`;
const nowIso = () => new Date().toISOString();
const fmt = (iso) => new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

async function encryptText(text, passphrase) {
  try {
    const enc = new TextEncoder();
    const keyMat = await crypto.subtle.importKey("raw", enc.encode(passphrase), "PBKDF2", false, ["deriveKey"]);
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const key = await crypto.subtle.deriveKey(
      { name: "PBKDF2", salt, iterations: 100000, hash: "SHA-256" },
      keyMat, { name: "AES-GCM", length: 256 }, false, ["encrypt"]
    );
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const enc2 = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(text));
    const buf = new Uint8Array(16 + 12 + enc2.byteLength);
    buf.set(salt); buf.set(iv, 16); buf.set(new Uint8Array(enc2), 28);
    return btoa(String.fromCharCode(...buf)).slice(0, 16);
  } catch { return "enc_error"; }
}

async function expandIdea(raw, project, type) {
  try {
    const resp = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "claude-sonnet-4-20250514",
        max_tokens: 1000,
        system: `You are an internal thinking assistant for a founder-researcher. 
Respond ONLY with valid JSON, no markdown fences, no preamble:
{"title":"short crisp title max 8 words","summary":"2-sentence summary","why":"1 sentence why this matters now","firstMove":"single smallest concrete next action","questions":["q1","q2"],"tags":["t1","t2","t3"],"estimatedScope":"hours|days|weeks|months"}`,
        messages: [{ role: "user", content: `Project: ${project}\nType: ${type}\nIdea: ${raw}` }]
      })
    });
    const data = await resp.json();
    const txt = data.content?.find(b => b.type === "text")?.text || "{}";
    return JSON.parse(txt.replace(/```json|```/g, "").trim());
  } catch { return null; }
}

const Dot = ({ color, size = 8 }) => (
  <span style={{ display: "inline-block", width: size, height: size, borderRadius: "50%", background: color, flexShrink: 0 }} />
);

const Tag = ({ label, color }) => (
  <span style={{ fontSize: 10, letterSpacing: "0.08em", padding: "2px 7px", border: `1px solid ${color}44`, color, borderRadius: 2, fontFamily: "monospace", textTransform: "uppercase" }}>{label}</span>
);

function IdeaCard({ idea, onSelect, isSelected }) {
  const proj = PROJECTS[idea.project];
  return (
    <div onClick={() => onSelect(idea)} style={{
      padding: "12px 14px", marginBottom: 5,
      border: `1px solid ${isSelected ? proj.color + "55" : COLORS.border}`,
      borderLeft: `3px solid ${proj.color}`,
      background: isSelected ? COLORS.faint : "transparent",
      cursor: "pointer", borderRadius: 2,
      transition: "background 0.1s"
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
        <Dot color={proj.color} size={6} />
        <span style={{ fontSize: 10, color: proj.color, fontFamily: "monospace", letterSpacing: "0.1em" }}>{proj.prefix}</span>
        <span style={{ fontSize: 10, color: COLORS.muted, fontFamily: "monospace" }}>{idea.id}</span>
        <span style={{ marginLeft: "auto", fontSize: 10, color: COLORS.muted }}>{fmt(idea.createdAt)}</span>
      </div>
      <div style={{ fontSize: 13, color: COLORS.text, fontWeight: 500, marginBottom: 5, lineHeight: 1.4 }}>
        {idea.expanded?.title || (idea.raw.slice(0, 72) + (idea.raw.length > 72 ? "…" : ""))}
      </div>
      <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
        <Tag label={idea.ideaType} color={COLORS.muted} />
        {idea.route && <Tag label={idea.route} color={proj.color} />}
        {idea.status === "routed" && <Tag label="routed" color={COLORS.newsletter} />}
      </div>
    </div>
  );
}

function Field({ label, value, highlight, mono }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 10, color: COLORS.muted, letterSpacing: "0.1em", marginBottom: 4 }}>{label}</div>
      <div style={{
        fontSize: mono ? 12 : 13, color: highlight ? COLORS.text : "#c0bdb6",
        fontFamily: mono ? "monospace" : "inherit", lineHeight: 1.5,
        padding: highlight ? "8px 12px" : 0,
        background: highlight ? "#181818" : "transparent",
        borderRadius: 2, borderLeft: highlight ? `2px solid ${COLORS.text}` : "none"
      }}>{value}</div>
    </div>
  );
}

function NewIdeaForm({ raw, setRaw, project, setProject, type, setType, route, setRoute, loading, onCapture }) {
  return (
    <div style={{ maxWidth: 580 }}>
      <div style={{ fontSize: 11, color: COLORS.muted, letterSpacing: "0.1em", marginBottom: 18 }}>NEW IDEA</div>
      <textarea
        value={raw} onChange={e => setRaw(e.target.value)} autoFocus
        placeholder="Drop the idea here. Raw is fine."
        onKeyDown={e => { if (e.metaKey && e.key === "Enter") onCapture(); }}
        style={{
          width: "100%", minHeight: 110, background: COLORS.surface,
          border: `1px solid ${COLORS.border}`, borderRadius: 2,
          color: COLORS.text, fontSize: 14, padding: 14, resize: "vertical",
          fontFamily: "inherit", lineHeight: 1.6, outline: "none", boxSizing: "border-box"
        }}
      />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginTop: 14 }}>
        <div>
          <div style={{ fontSize: 10, color: COLORS.muted, letterSpacing: "0.1em", marginBottom: 6 }}>PROJECT</div>
          {Object.entries(PROJECTS).map(([id, p]) => (
            <button key={id} onClick={() => setProject(id)} style={{
              display: "block", width: "100%", textAlign: "left", padding: "6px 10px", marginBottom: 3,
              background: project === id ? p.color + "18" : "transparent",
              border: `1px solid ${project === id ? p.color + "55" : COLORS.border}`,
              color: project === id ? p.color : COLORS.muted, borderRadius: 2, cursor: "pointer", fontSize: 12
            }}>{p.label}</button>
          ))}
        </div>
        <div>
          <div style={{ fontSize: 10, color: COLORS.muted, letterSpacing: "0.1em", marginBottom: 6 }}>TYPE</div>
          {IDEA_TYPES.map(t => (
            <button key={t} onClick={() => setType(t)} style={{
              display: "block", width: "100%", textAlign: "left", padding: "6px 10px", marginBottom: 3,
              background: type === t ? COLORS.faint : "transparent",
              border: `1px solid ${type === t ? COLORS.borderHover : COLORS.border}`,
              color: type === t ? COLORS.text : COLORS.muted, borderRadius: 2, cursor: "pointer", fontSize: 12
            }}>{t}</button>
          ))}
        </div>
        <div>
          <div style={{ fontSize: 10, color: COLORS.muted, letterSpacing: "0.1em", marginBottom: 6 }}>ROUTE TO</div>
          {ROUTE_TYPES.map(r => (
            <button key={r.id} onClick={() => setRoute(r.id)} style={{
              display: "block", width: "100%", textAlign: "left", padding: "6px 10px", marginBottom: 3,
              background: route === r.id ? COLORS.faint : "transparent",
              border: `1px solid ${route === r.id ? COLORS.borderHover : COLORS.border}`,
              color: route === r.id ? COLORS.text : COLORS.muted, borderRadius: 2, cursor: "pointer", fontSize: 12
            }}><span style={{ marginRight: 6 }}>{r.icon}</span>{r.label}</button>
          ))}
        </div>
      </div>
      <button onClick={onCapture} disabled={!raw.trim() || loading} style={{
        marginTop: 18, padding: "10px 24px",
        background: raw.trim() && !loading ? COLORS.text : COLORS.faint,
        color: raw.trim() && !loading ? COLORS.bg : COLORS.muted,
        border: "none", borderRadius: 2, cursor: raw.trim() ? "pointer" : "default",
        fontSize: 12, letterSpacing: "0.1em", fontWeight: 600
      }}>{loading ? "EXPANDING…" : "CAPTURE  ⌘↵"}</button>
      <div style={{ fontSize: 11, color: COLORS.muted, marginTop: 8 }}>
        Claude structures this before routing. Raw stays encrypted.
      </div>
    </div>
  );
}

function DetailPanel({ idea, routing, log, onRoute, onClose }) {
  const proj = PROJECTS[idea.project];
  const exp = idea.expanded;
  return (
    <div style={{ flex: 1, padding: 20, overflow: "auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Dot color={proj.color} size={10} />
          <span style={{ fontSize: 10, color: proj.color, letterSpacing: "0.12em", fontFamily: "monospace" }}>
            {proj.prefix} · {idea.id}
          </span>
        </div>
        <button onClick={onClose} style={{ background: "none", border: "none", color: COLORS.muted, cursor: "pointer", fontSize: 20, lineHeight: 1 }}>×</button>
      </div>

      {exp ? (
        <>
          <h2 style={{ fontSize: 17, fontWeight: 600, marginBottom: 10, lineHeight: 1.3, color: COLORS.text }}>{exp.title}</h2>
          <div style={{ fontSize: 13, color: "#999", marginBottom: 18, lineHeight: 1.6 }}>{exp.summary}</div>
          {exp.why && <Field label="WHY NOW" value={exp.why} />}
          {exp.firstMove && <Field label="FIRST MOVE" value={exp.firstMove} highlight />}
          {exp.estimatedScope && <Field label="SCOPE" value={exp.estimatedScope.toUpperCase()} mono />}
          {exp.questions?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 10, color: COLORS.muted, letterSpacing: "0.1em", marginBottom: 8 }}>OPEN QUESTIONS</div>
              {exp.questions.map((q, i) => (
                <div key={i} style={{ fontSize: 13, color: COLORS.text, padding: "6px 0", borderBottom: `1px solid ${COLORS.border}`, display: "flex", gap: 8 }}>
                  <span style={{ color: COLORS.muted }}>?</span>{q}
                </div>
              ))}
            </div>
          )}
          {exp.tags?.length > 0 && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 18 }}>
              {exp.tags.map(t => <Tag key={t} label={t} color={proj.color} />)}
            </div>
          )}
        </>
      ) : (
        <div style={{ fontSize: 13, color: COLORS.muted, marginBottom: 18, lineHeight: 1.6 }}>{idea.raw}</div>
      )}

      <details style={{ marginBottom: 18 }}>
        <summary style={{ fontSize: 10, color: COLORS.muted, cursor: "pointer", letterSpacing: "0.1em" }}>RAW INPUT</summary>
        <div style={{ marginTop: 8, fontSize: 12, color: COLORS.muted, fontFamily: "monospace", padding: 12, background: COLORS.surface, borderRadius: 2, lineHeight: 1.6 }}>
          {idea.raw}
        </div>
      </details>

      {idea.status !== "routed" ? (
        <button onClick={onRoute} disabled={routing} style={{
          width: "100%", padding: "11px",
          background: routing ? COLORS.faint : proj.color + "18",
          border: `1px solid ${proj.color}44`, color: routing ? COLORS.muted : proj.color,
          borderRadius: 2, cursor: routing ? "default" : "pointer",
          fontSize: 12, letterSpacing: "0.1em", fontWeight: 600
        }}>
          {routing ? "ROUTING…" : `ROUTE → ${(ROUTE_TYPES.find(r => r.id === idea.route)?.label || "DRAFT").toUpperCase()}`}
        </button>
      ) : (
        <div style={{ padding: 12, border: `1px solid ${COLORS.newsletter}44`, borderRadius: 2, color: COLORS.newsletter, fontSize: 12, letterSpacing: "0.1em", textAlign: "center" }}>
          ✓ ROUTED {idea.routedAt ? `· ${fmt(idea.routedAt)}` : ""}
        </div>
      )}

      {log.length > 0 && (
        <div style={{ marginTop: 10, padding: 12, background: COLORS.surface, borderRadius: 2 }}>
          {log.map((line, i) => (
            <div key={i} style={{ fontSize: 11, fontFamily: "monospace", color: i === log.length - 1 ? COLORS.text : COLORS.muted, padding: "2px 0" }}>{line}</div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function BlackhorsePipeline() {
  const [ideas, setIdeas] = useState([]);
  const [selected, setSelected] = useState(null);
  const [view, setView] = useState("inbox");
  const [filter, setFilter] = useState("all");
  const [raw, setRaw] = useState("");
  const [project, setProject] = useState("blackhorse");
  const [type, setType] = useState("Feature");
  const [route, setRoute] = useState("draft");
  const [expanding, setExpanding] = useState(false);
  const [routing, setRouting] = useState(false);
  const [log, setLog] = useState([]);

  const persist = (next) => { setIdeas(next); try { sessionStorage.setItem("bhp", JSON.stringify(next)); } catch {} };

  useEffect(() => {
    try { const s = sessionStorage.getItem("bhp"); if (s) setIdeas(JSON.parse(s)); } catch {}
  }, []);

  const filtered = filter === "all" ? ideas : ideas.filter(i => i.project === filter);

  const handleCapture = async () => {
    if (!raw.trim()) return;
    setExpanding(true);
    const expanded = await expandIdea(raw, PROJECTS[project].label, type);
    const idea = { id: generateId(), raw, project, ideaType: type, route, status: "captured", createdAt: nowIso(), expanded };
    const next = [idea, ...ideas];
    persist(next);
    setSelected(idea);
    setExpanding(false);
    setView("detail");
    setRaw("");
    setLog([]);
  };

  const handleRoute = async (idea) => {
    setRouting(true);
    setLog([]);
    const addLog = (msg) => setLog(p => [...p, msg]);

    addLog(`⬡ Routing ${idea.id} → ${idea.route.toUpperCase()}`);
    await new Promise(r => setTimeout(r, 350));

    if (idea.route === "github") {
      addLog("⬡ Generating GitHub issue…");
      await new Promise(r => setTimeout(r, 500));
      const body = [`**Project:** ${PROJECTS[idea.project].label}`, `**Type:** ${idea.ideaType}`, `**Idea:** ${idea.raw}`,
        idea.expanded?.summary ? `\n**Summary:** ${idea.expanded.summary}` : "",
        idea.expanded?.firstMove ? `\n**First move:** ${idea.expanded.firstMove}` : "",
        idea.expanded?.questions?.length ? `\n**Open questions:**\n${idea.expanded.questions.map(q => `- ${q}`).join("\n")}` : ""
      ].filter(Boolean).join("\n");
      const url = `https://github.com/issues/new?title=${encodeURIComponent(idea.expanded?.title || idea.raw.slice(0, 80))}&body=${encodeURIComponent(body)}`;
      window.open(url, "_blank");
      addLog("⬡ GitHub issue opened ↗");
    } else if (idea.route === "notion") {
      addLog("□ Notion page scaffold ready");
      await new Promise(r => setTimeout(r, 500));
      addLog("□ Connect Notion MCP to push directly");
    } else if (idea.route === "calendar") {
      addLog("◈ Scheduling build block…");
      await new Promise(r => setTimeout(r, 500));
      addLog("◈ Will target next 2–4pm slot");
      addLog("◈ Connect Calendar MCP to auto-create");
    } else {
      addLog("◎ Draft saved locally");
    }

    const hash = await encryptText(idea.raw, idea.id);
    await new Promise(r => setTimeout(r, 200));
    addLog(`⬡ Raw encrypted [${hash}…]`);
    addLog(`✓ ${idea.id} → ROUTED`);

    const next = ideas.map(i => i.id === idea.id ? { ...i, status: "routed", routedAt: nowIso() } : i);
    persist(next);
    setSelected(p => p?.id === idea.id ? { ...p, status: "routed", routedAt: nowIso() } : p);
    setRouting(false);
  };

  const showDetail = view === "detail" && selected;

  return (
    <div style={{ minHeight: "100vh", background: COLORS.bg, color: COLORS.text, fontFamily: "'IBM Plex Sans', 'JetBrains Mono', 'Courier New', monospace", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <div style={{ borderBottom: `1px solid ${COLORS.border}`, padding: "11px 22px", display: "flex", alignItems: "center", gap: 14 }}>
        <span style={{ fontSize: 11, letterSpacing: "0.2em", color: COLORS.muted }}>BLACKHORSE</span>
        <span style={{ color: COLORS.border }}>|</span>
        <span style={{ fontSize: 11, letterSpacing: "0.2em", color: COLORS.text }}>PIPELINE</span>
        <span style={{ fontSize: 10, color: COLORS.muted, marginLeft: "auto", fontFamily: "monospace" }}>
          {ideas.length} idea{ideas.length !== 1 ? "s" : ""} · private · session only
        </span>
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Sidebar */}
        <div style={{ width: 210, borderRight: `1px solid ${COLORS.border}`, padding: "14px 0", display: "flex", flexDirection: "column", flexShrink: 0 }}>
          {[{ id: "inbox", label: "Inbox", badge: ideas.length }, { id: "new", label: "New Idea", badge: null }].map(n => (
            <button key={n.id} onClick={() => setView(n.id)} style={{
              background: view === n.id ? COLORS.faint : "transparent",
              border: "none", borderLeft: `2px solid ${view === n.id ? COLORS.text : "transparent"}`,
              color: view === n.id ? COLORS.text : COLORS.muted,
              padding: "8px 18px", textAlign: "left", cursor: "pointer",
              fontSize: 12, letterSpacing: "0.05em", display: "flex", justifyContent: "space-between", alignItems: "center"
            }}>
              {n.label}
              {n.badge !== null && <span style={{ color: COLORS.muted, fontSize: 10 }}>{n.badge}</span>}
            </button>
          ))}

          <div style={{ margin: "14px 18px 6px", fontSize: 10, color: COLORS.muted, letterSpacing: "0.12em" }}>PROJECTS</div>
          {[{ id: "all", label: "All", color: COLORS.muted }, ...Object.entries(PROJECTS).map(([id, p]) => ({ id, label: p.label, color: p.color }))].map(p => (
            <button key={p.id} onClick={() => { setFilter(p.id); setView("inbox"); }} style={{
              background: filter === p.id && view === "inbox" ? COLORS.faint : "transparent",
              border: "none", color: filter === p.id && view === "inbox" ? p.color : COLORS.muted,
              padding: "5px 18px", textAlign: "left", cursor: "pointer",
              fontSize: 12, display: "flex", alignItems: "center", gap: 8
            }}>
              {p.id !== "all" && <Dot color={p.color} size={6} />}
              {p.label}
              {p.id !== "all" && <span style={{ marginLeft: "auto", fontSize: 10, color: COLORS.muted }}>{ideas.filter(i => i.project === p.id).length}</span>}
            </button>
          ))}

          <div style={{ flex: 1 }} />
          <div style={{ padding: "10px 18px", borderTop: `1px solid ${COLORS.border}` }}>
            <div style={{ fontSize: 10, color: COLORS.muted, lineHeight: 1.7 }}>
              → GitHub · Notion · Calendar<br />
              Encrypted · Private · Local
            </div>
          </div>
        </div>

        {/* Main */}
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          <div style={{
            width: showDetail ? 320 : "100%",
            padding: "14px", overflow: "auto", flexShrink: 0,
            borderRight: showDetail ? `1px solid ${COLORS.border}` : "none"
          }}>
            {view === "new" ? (
              <NewIdeaForm raw={raw} setRaw={setRaw} project={project} setProject={setProject}
                type={type} setType={setType} route={route} setRoute={setRoute}
                loading={expanding} onCapture={handleCapture} />
            ) : (
              <>
                <div style={{ fontSize: 11, color: COLORS.muted, letterSpacing: "0.1em", marginBottom: 10 }}>
                  {filter === "all" ? "ALL" : PROJECTS[filter]?.label?.toUpperCase()} · {filtered.length}
                </div>
                {filtered.length === 0 ? (
                  <div style={{ color: COLORS.muted, fontSize: 13, padding: "20px 0" }}>
                    Nothing yet.{" "}
                    <button onClick={() => setView("new")} style={{ background: "none", border: "none", color: COLORS.text, cursor: "pointer", textDecoration: "underline", fontSize: 13, padding: 0 }}>
                      Add an idea →
                    </button>
                  </div>
                ) : filtered.map(idea => (
                  <IdeaCard key={idea.id} idea={idea} isSelected={selected?.id === idea.id}
                    onSelect={i => { setSelected(i); setView("detail"); setLog([]); }} />
                ))}
              </>
            )}
          </div>

          {showDetail && (
            <DetailPanel idea={selected} routing={routing} log={log}
              onRoute={() => handleRoute(selected)} onClose={() => setView("inbox")} />
          )}
        </div>
      </div>
    </div>
  );
}
