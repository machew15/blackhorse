import { useState, useRef, useEffect, useCallback } from "react";

const DEFAULT_SYSTEM = `You are a focused assistant. Be direct, sharp, and useful. No filler.`;

function fileToBase64(file) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(r.result.split(",")[1]);
    r.onerror = () => rej(new Error("Read failed"));
    r.readAsDataURL(file);
  });
}

export default function App() {
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM);
  const [editingSystem, setEditingSystem] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showSystem, setShowSystem] = useState(true);
  const [pendingImages, setPendingImages] = useState([]);
  const [dragging, setDragging] = useState(false);
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [input]);

  async function addImageFile(file) {
    if (!file.type.startsWith("image/")) return;
    const base64 = await fileToBase64(file);
    const previewUrl = URL.createObjectURL(file);
    setPendingImages(imgs => [...imgs, { base64, mediaType: file.type, previewUrl }]);
  }

  const handleDrop = useCallback(async (e) => {
    e.preventDefault();
    setDragging(false);
    for (const f of Array.from(e.dataTransfer.files)) await addImageFile(f);
  }, []);

  const handleDragOver = (e) => { e.preventDefault(); setDragging(true); };
  const handleDragLeave = () => setDragging(false);

  async function handlePaste(e) {
    for (const item of Array.from(e.clipboardData?.items || [])) {
      if (item.type.startsWith("image/")) {
        const file = item.getAsFile();
        if (file) await addImageFile(file);
      }
    }
  }

  async function send() {
    const text = input.trim();
    if ((!text && pendingImages.length === 0) || loading) return;

    let userContent;
    if (pendingImages.length > 0) {
      userContent = [
        ...pendingImages.map(img => ({
          type: "image",
          source: { type: "base64", media_type: img.mediaType, data: img.base64 },
        })),
        ...(text ? [{ type: "text", text }] : []),
      ];
    } else {
      userContent = text;
    }

    const displayMessage = { role: "user", content: userContent, _previews: pendingImages.map(i => i.previewUrl) };
    const newMessages = [...messages, displayMessage];
    const apiMessages = [...messages.map(m => ({ role: m.role, content: m.content })), { role: "user", content: userContent }];

    setMessages(newMessages);
    setPendingImages([]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 1000,
          system: systemPrompt,
          messages: apiMessages,
        }),
      });
      const data = await res.json();
      const reply = data.content?.find(b => b.type === "text")?.text || "(no response)";
      setMessages(prev => [...prev, { role: "assistant", content: reply }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: "assistant", content: `Error: ${e.message}` }]);
    }
    setLoading(false);
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  }

  function renderContent(m) {
    if (typeof m.content === "string") return <span style={{ whiteSpace: "pre-wrap" }}>{m.content}</span>;
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {m._previews?.map((url, i) => (
          <img key={i} src={url} alt="" style={{ maxWidth: "260px", maxHeight: "200px", borderRadius: "6px", objectFit: "contain", border: "1px solid #2a2a2a" }} />
        ))}
        {Array.isArray(m.content) && m.content.filter(b => b.type === "text").map((b, i) => (
          <span key={i} style={{ whiteSpace: "pre-wrap" }}>{b.text}</span>
        ))}
      </div>
    );
  }

  const canSend = !loading && (input.trim() || pendingImages.length > 0);

  return (
    <div
      style={{
        fontFamily: "'Berkeley Mono', 'Fira Mono', 'Courier New', monospace",
        background: "#0a0a0a", color: "#e8e8e8", minHeight: "100vh",
        display: "flex", flexDirection: "column", maxWidth: "780px", margin: "0 auto",
        outline: dragging ? "2px dashed #2a2a2a" : "none", transition: "outline 0.1s",
      }}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
    >
      {dragging && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 100, pointerEvents: "none",
          display: "flex", alignItems: "center", justifyContent: "center",
          background: "rgba(10,10,10,0.88)",
        }}>
          <div style={{ fontSize: "13px", color: "#3a3a3a", letterSpacing: "0.14em" }}>DROP IMAGE</div>
        </div>
      )}

      {/* Header */}
      <div style={{
        borderBottom: "1px solid #222", padding: "14px 20px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: "#0a0a0a", position: "sticky", top: 0, zIndex: 10,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div style={{
            width: "8px", height: "8px", borderRadius: "50%",
            background: loading ? "#f59e0b" : "#22c55e",
            boxShadow: loading ? "0 0 6px #f59e0b" : "0 0 6px #22c55e",
            transition: "all 0.3s",
          }} />
          <span style={{ fontSize: "13px", color: "#666", letterSpacing: "0.08em" }}>PRIVATE CHANNEL</span>
        </div>
        <div style={{ display: "flex", gap: "12px" }}>
          <button onClick={() => setShowSystem(s => !s)} style={btnStyle}>{showSystem ? "hide prompt" : "show prompt"}</button>
          <button onClick={() => setMessages([])} style={btnStyle}>clear</button>
        </div>
      </div>

      {/* System Prompt */}
      {showSystem && (
        <div style={{ margin: "16px 20px 0", border: "1px solid #1e1e1e", borderRadius: "6px", overflow: "hidden" }}>
          <div style={{
            background: "#111", padding: "8px 14px", fontSize: "11px", color: "#444",
            letterSpacing: "0.1em", display: "flex", justifyContent: "space-between", alignItems: "center",
          }}>
            <span>SYSTEM PROMPT</span>
            <button onClick={() => setEditingSystem(e => !e)} style={{ ...btnStyle, fontSize: "11px" }}>
              {editingSystem ? "done" : "edit"}
            </button>
          </div>
          {editingSystem ? (
            <textarea value={systemPrompt} onChange={e => setSystemPrompt(e.target.value)} style={{
              width: "100%", background: "#0d0d0d", color: "#ccc", border: "none",
              padding: "14px", fontSize: "13px", fontFamily: "inherit", resize: "vertical",
              minHeight: "80px", outline: "none", boxSizing: "border-box", lineHeight: "1.6",
            }} />
          ) : (
            <div style={{ background: "#0d0d0d", padding: "14px", fontSize: "13px", color: "#555", lineHeight: "1.6", whiteSpace: "pre-wrap" }}>
              {systemPrompt}
            </div>
          )}
        </div>
      )}

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
        {messages.length === 0 && (
          <div style={{ textAlign: "center", color: "#2a2a2a", fontSize: "13px", marginTop: "60px", letterSpacing: "0.05em" }}>
            set your system prompt · drop, paste, or attach images · start talking
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: m.role === "user" ? "flex-end" : "flex-start" }}>
            <div style={{
              maxWidth: "85%", padding: "12px 16px",
              borderRadius: m.role === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
              background: m.role === "user" ? "#1a1a1a" : "#111",
              border: m.role === "user" ? "1px solid #2a2a2a" : "1px solid #1a1a1a",
              fontSize: "14px", lineHeight: "1.65",
              color: m.role === "user" ? "#d4d4d4" : "#b0b0b0",
              wordBreak: "break-word",
            }}>
              {renderContent(m)}
            </div>
            <div style={{ fontSize: "10px", color: "#2a2a2a", marginTop: "4px", letterSpacing: "0.06em" }}>
              {m.role === "user" ? "you" : "model"}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: "flex", alignItems: "flex-start" }}>
            <div style={{
              padding: "12px 16px", borderRadius: "12px 12px 12px 2px",
              background: "#111", border: "1px solid #1a1a1a",
              display: "flex", gap: "5px", alignItems: "center",
            }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{
                  width: "5px", height: "5px", borderRadius: "50%", background: "#333",
                  animation: "pulse 1.2s infinite", animationDelay: `${i * 0.2}s`,
                }} />
              ))}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ padding: "16px 20px", borderTop: "1px solid #161616", background: "#0a0a0a", position: "sticky", bottom: 0 }}>
        {pendingImages.length > 0 && (
          <div style={{ display: "flex", gap: "8px", marginBottom: "10px", flexWrap: "wrap" }}>
            {pendingImages.map((img, i) => (
              <div key={i} style={{ position: "relative" }}>
                <img src={img.previewUrl} alt="" style={{
                  width: "60px", height: "60px", objectFit: "cover",
                  borderRadius: "6px", border: "1px solid #2a2a2a",
                }} />
                <button onClick={() => setPendingImages(imgs => imgs.filter((_, j) => j !== i))} style={{
                  position: "absolute", top: "-6px", right: "-6px",
                  width: "16px", height: "16px", borderRadius: "50%",
                  background: "#222", border: "1px solid #333", color: "#888",
                  fontSize: "11px", cursor: "pointer", display: "flex",
                  alignItems: "center", justifyContent: "center", lineHeight: 1, padding: 0,
                }}>×</button>
              </div>
            ))}
          </div>
        )}

        <div style={{
          display: "flex", gap: "10px", alignItems: "flex-end",
          background: "#111", border: "1px solid #222", borderRadius: "10px", padding: "10px 14px",
        }}>
          <button onClick={() => fileInputRef.current?.click()} title="Attach image" style={{
            ...btnStyle, padding: "5px 9px", fontSize: "16px",
            flexShrink: 0, alignSelf: "flex-end", marginBottom: "1px",
          }}>⊕</button>
          <input ref={fileInputRef} type="file" accept="image/*" multiple style={{ display: "none" }}
            onChange={async e => {
              for (const f of Array.from(e.target.files || [])) await addImageFile(f);
              e.target.value = "";
            }}
          />
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            onPaste={handlePaste}
            placeholder="say something · paste or drop images..."
            rows={1}
            style={{
              flex: 1, background: "transparent", border: "none", outline: "none",
              color: "#e8e8e8", fontSize: "14px", fontFamily: "inherit",
              resize: "none", lineHeight: "1.5", maxHeight: "160px", overflowY: "auto", padding: 0,
            }}
          />
          <button onClick={send} disabled={!canSend} style={{
            background: canSend ? "#e8e8e8" : "#1a1a1a",
            color: canSend ? "#0a0a0a" : "#333",
            border: "none", borderRadius: "6px", padding: "7px 14px",
            fontSize: "12px", fontFamily: "inherit",
            cursor: canSend ? "pointer" : "default",
            transition: "all 0.15s", letterSpacing: "0.05em", whiteSpace: "nowrap",
          }}>send</button>
        </div>
        <div style={{ fontSize: "10px", color: "#222", marginTop: "8px", textAlign: "center", letterSpacing: "0.06em" }}>
          shift+enter for newline · enter to send · paste or drop images anywhere
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.2; transform: scale(0.8); }
          50% { opacity: 1; transform: scale(1.1); }
        }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #1e1e1e; border-radius: 2px; }
      `}</style>
    </div>
  );
}

const btnStyle = {
  background: "transparent", border: "1px solid #222", color: "#444",
  padding: "4px 10px", borderRadius: "4px", fontSize: "11px",
  fontFamily: "inherit", cursor: "pointer", letterSpacing: "0.06em", transition: "all 0.15s",
};
