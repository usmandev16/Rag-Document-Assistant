import { useEffect, useRef, useState } from "react";
import { createChat, getChatById, getChats, getDocuments, sendChat, uploadDocuments } from "./api.js";

function docIcon(name) {
  const lower = name.toLowerCase();
  return lower.endsWith(".xlsx") || lower.endsWith(".csv") || lower.endsWith(".xls") ? "📊" : "📄";
}

function nowLabel() {
  return new Date().toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  }).replace(",", " ·");
}

function docTimeLabel(isoString) {
  if (!isoString) return "";
  const date = new Date(isoString);
  const now = new Date();
  const minutesAgo = (now - date) / 60000;
  if (minutesAgo < 1) return "Now";
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  }
  if ((now - date) / 86400000 < 7) {
    return date.toLocaleDateString("en-US", { weekday: "short" });
  }
  return date.toLocaleDateString("en-US", { day: "numeric", month: "short" });
}

function IconRail({ theme, onToggleTheme, onExit }) {
  return (
    <div className="icon-rail">
      <div className="rail-brand" title="Doc Chat">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.9 5.6a4 4 0 0 0 2.5 2.5L22 12l-5.6 1.9a4 4 0 0 0-2.5 2.5L12 22l-1.9-5.6a4 4 0 0 0-2.5-2.5L2 12l5.6-1.9a4 4 0 0 0 2.5-2.5L12 2z"/></svg>
      </div>
      <div className="rail-item active" title="Chats">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
      </div>
      <div className="rail-spacer"></div>
      <div className="rail-item rail-green" title="Sign out" onClick={onExit}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
      </div>
      <div className="rail-divider"></div>
      <div className="rail-theme" title="Theme">
        <button
          className={`theme-icon theme-icon-moon${theme === "dark" ? " active" : ""}`}
          title="Dark mode"
          onClick={() => onToggleTheme("dark")}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        </button>
        <button
          className={`theme-icon theme-icon-sun${theme === "light" ? " active" : ""}`}
          title="Light mode"
          onClick={() => onToggleTheme("light")}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
        </button>
      </div>
    </div>
  );
}

function MessageActions() {
  return (
    <div className="msg-actions">
      <button className="react" title="Good response">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
      </button>
      <button className="react" title="Bad response">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"/></svg>
      </button>
      <span className="spacer"></span>
      <span className="pill">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
        Generate Response
      </span>
      <span className="pill">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
        Copy
      </span>
      <button className="icon-ghost">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
      </button>
    </div>
  );
}

function WebSearchPanel({ meta }) {
  const when = meta.searched_at
    ? new Date(meta.searched_at).toLocaleString("en-US", {
        month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit",
      })
    : null;
  const queries = meta.queries || [];
  const sources = meta.sources || [];

  return (
    <>
      <div className="web-caption">🌐 Live web search{when ? ` · searched ${when}` : ""}</div>
      {(queries.length > 0 || sources.length > 0) && (
        <details className="expander">
          <summary>🔎 How this was researched · {sources.length} source{sources.length === 1 ? "" : "s"}</summary>
          <div className="expander-body">
            {queries.length > 0 && (
              <>
                <div className="sb-label" style={{ margin: "0.5rem 0 0.3rem" }}>Web searches run</div>
                {queries.map((q, i) => <div className="query-line" key={i}>🔍 {q}</div>)}
              </>
            )}
            {sources.length > 0 && (
              <>
                <div className="sb-label" style={{ margin: "0.7rem 0 0.3rem" }}>Sources read</div>
                {sources.map((s, i) => (
                  <div className="result-line" key={i}>
                    <a href={s.url} target="_blank" rel="noreferrer">{s.title}</a>
                    {typeof s.score === "number" ? `  ·  ${Math.round(s.score * 100)}% match` : ""}
                  </div>
                ))}
              </>
            )}
          </div>
        </details>
      )}
    </>
  );
}

function SourcesPanel({ sources }) {
  const docCount = new Set(sources.map((s) => s.source)).size;
  return (
    <details className="expander">
      <summary>📎 Sources ({sources.length} chunks · {docCount} doc{docCount === 1 ? "" : "s"})</summary>
      <div className="expander-body">
        {sources.map((s, i) => (
          <div className="source-item" key={i}>
            <div className="source-head"><b>{s.source}</b> · chunk {s.chunk_index}</div>
            <div className="source-text">{s.text}</div>
          </div>
        ))}
      </div>
    </details>
  );
}

function Message({ message }) {
  const isUser = message.role === "user";
  return (
    <div className={`message ${message.role}`}>
      <div className="message-avatar">
        {isUser ? (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.9 5.6a4 4 0 0 0 2.5 2.5L22 12l-5.6 1.9a4 4 0 0 0-2.5 2.5L12 22l-1.9-5.6a4 4 0 0 0-2.5-2.5L2 12l5.6-1.9a4 4 0 0 0 2.5-2.5L12 2z"/></svg>
        )}
      </div>
      <div className="message-body">
        <div className="msg-meta">
          <span className="msg-role">{isUser ? "You" : "AI"}</span>
          {message.time && <span className="msg-time">{message.time}</span>}
        </div>
        {message.attachments && message.attachments.length > 0 && (
          <div className="msg-attachments">
            {message.attachments.map((name) => (
              <div className="msg-attachment-chip" key={name}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/></svg>
                <span>{name}</span>
              </div>
            ))}
          </div>
        )}
        {message.content && <div className="msg-content">{message.content}</div>}
        {message.error && <div className="error-box">⚠️ Check that GROQ_API_KEY is set and valid. ({message.error})</div>}
        {message.sources && message.sources.length > 0 && <SourcesPanel sources={message.sources} />}
        {message.web_search && <WebSearchPanel meta={message.web_search} />}
        {!isUser && <MessageActions />}
      </div>
    </div>
  );
}

export default function App({ onExit }) {
  const [indexedDocs, setIndexedDocs] = useState([]);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);
  const [chats, setChats] = useState([]);
  const [currentChatId, setCurrentChatId] = useState(null);
  const [activeTab, setActiveTab] = useState("chats");
  const [chatSearch, setChatSearch] = useState("");
  const [messageSearchOpen, setMessageSearchOpen] = useState(false);
  const [messageSearch, setMessageSearch] = useState("");
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "light");
  const [attachments, setAttachments] = useState([]);
  const scrollRef = useRef(null);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    getChats().then(setChats);
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function ensureChatId() {
    if (currentChatId) return currentChatId;
    const chat = await createChat();
    setChats((prev) => [{ id: chat.id, title: chat.title, updated_at: chat.updated_at, preview: "No messages yet." }, ...prev]);
    setCurrentChatId(chat.id);
    return chat.id;
  }

  async function handleAttach(fileList) {
    const indexedNames = new Set(indexedDocs.map((d) => d.name));
    const files = Array.from(fileList || []).filter((f) => !indexedNames.has(f.name));
    if (files.length === 0) return;
    const names = files.map((f) => f.name);
    setAttachments((prev) => [...prev, ...names.map((name) => ({ name, status: "uploading" }))]);
    try {
      const chatId = await ensureChatId();
      const result = await uploadDocuments(files, chatId);
      setIndexedDocs((prev) => [...prev, ...result.indexed]);
      setAttachments((prev) => prev.map((a) => (names.includes(a.name) ? { ...a, status: "ready" } : a)));
    } catch {
      setAttachments((prev) => prev.filter((a) => !names.includes(a.name)));
    }
  }

  function removeAttachment(name) {
    setAttachments((prev) => prev.filter((a) => a.name !== name));
  }

  function handleChatDrop(e) {
    e.preventDefault();
    handleAttach(e.dataTransfer.files);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const trimmed = question.trim();
    if ((!trimmed && attachments.length === 0) || sending) return;

    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    const attachedNames = attachments.map((a) => a.name);
    const userMessage = {
      role: "user",
      content: trimmed,
      time: nowLabel(),
      attachments: attachedNames,
    };
    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    setAttachments([]);

    // Sent with just an attachment and no question: don't run it through
    // Q&A (there's nothing to answer), just confirm the upload.
    if (!trimmed && attachedNames.length > 0) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          time: nowLabel(),
          content: `Uploaded ${attachedNames.join(", ")}. Ask a question, or should I summarize it?`,
        },
      ]);
      return;
    }

    setSending(true);
    try {
      const res = await sendChat(trimmed, history, currentChatId);
      setMessages((prev) => [...prev, { role: "assistant", time: nowLabel(), content: res.answer, ...res }]);
      if (res.chat_id && res.chat_id !== currentChatId) setCurrentChatId(res.chat_id);
      getChats().then(setChats);
    } finally {
      setSending(false);
    }
  }

  async function handleNewChat() {
    const chat = await createChat();
    setChats((prev) => [{ id: chat.id, title: chat.title, updated_at: chat.updated_at, preview: "No messages yet." }, ...prev]);
    setCurrentChatId(chat.id);
    setMessages([]);
    setIndexedDocs([]);
    setActiveTab("chats");
  }

  async function handleSelectChat(id) {
    if (id === currentChatId) return;
    const chat = await getChatById(id);
    setMessages(chat.messages.map((m) => ({ role: m.role, content: m.content })));
    setCurrentChatId(id);
    getDocuments(id).then(setIndexedDocs);
  }

  const filteredChats = chats.filter(
    (c) => !chatSearch || c.title.toLowerCase().includes(chatSearch.toLowerCase())
  );

  const visibleMessages = messageSearch
    ? messages.filter((m) => m.content?.toLowerCase().includes(messageSearch.toLowerCase()))
    : messages;

  return (
    <>
      <IconRail theme={theme} onToggleTheme={setTheme} onExit={onExit} />
      <div className="app-shell">
        <aside className="sidebar">
          <div className="sb-head">
            <div className="sb-logo">
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.9 5.6a4 4 0 0 0 2.5 2.5L22 12l-5.6 1.9a4 4 0 0 0-2.5 2.5L12 22l-1.9-5.6a4 4 0 0 0-2.5-2.5L2 12l5.6-1.9a4 4 0 0 0 2.5-2.5L12 2z"/></svg>
            </div>
            <div className="sb-title">Chats</div>
            <button className="sb-add" title="New chat" onClick={handleNewChat}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            </button>
          </div>

          <div className="sb-tabs">
            <div className={`sb-tab${activeTab === "chats" ? " active" : ""}`} onClick={() => setActiveTab("chats")}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
              CHATS <span className="count">{chats.length}</span>
            </div>
            <div className={`sb-tab${activeTab === "saved" ? " active" : ""}`} onClick={() => setActiveTab("saved")}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
              SAVED <span className="count">0</span>
            </div>
          </div>
          <div className="sb-search-row">
            <div className="sb-search">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              <input
                type="text"
                placeholder="Search..."
                value={chatSearch}
                onChange={(e) => setChatSearch(e.target.value)}
              />
            </div>
          </div>

          <div className="sb-list">
            {activeTab === "chats" && (
              filteredChats.length === 0 ? (
                <p className="sb-caption">No chats yet — ask a question below to start one.</p>
              ) : (
                filteredChats.map((c) => (
                  <div
                    className={`doc-card chat-row${c.id === currentChatId ? " active" : ""}`}
                    key={c.id}
                    onClick={() => handleSelectChat(c.id)}
                    style={{ cursor: "pointer" }}
                  >
                    <div className="doc-card-body">
                      <div className="doc-card-top">
                        <div className="doc-card-name" title={c.title}>{c.title}</div>
                        <div className="doc-card-time">{docTimeLabel(c.updated_at)}</div>
                      </div>
                      <div className="doc-card-sub">{c.preview}</div>
                    </div>
                  </div>
                ))
              )
            )}

            {activeTab === "saved" && <p className="sb-caption">No saved chats yet.</p>}

            {activeTab === "docs" && (
              <>
                <div className="sb-label">Add to knowledge base</div>
                <p className="sb-caption">Upload one or more documents — answers can draw on all of them at once.</p>

                <label className="dropzone">
                  <input
                    type="file"
                    multiple
                    accept=".txt,.pdf,.docx,.xlsx,.csv"
                    onChange={(e) => handleAttach(e.target.files)}
                  />
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                  <span>{attachments.some((a) => a.status === "uploading") ? "Uploading…" : "Choose .txt, .pdf, .docx, .xlsx, or .csv files"}</span>
                </label>

                {indexedDocs.length > 0 && (
                  <>
                    <hr className="sb-divider" />
                    <div className="sb-label">Indexed documents</div>
                    {indexedDocs.map((doc, i) => (
                      <div className={`doc-card${i === indexedDocs.length - 1 ? " active" : ""}`} key={doc.name}>
                        <div className="doc-card-icon">{docIcon(doc.name)}</div>
                        <div className="doc-card-body">
                          <div className="doc-card-top">
                            <div className="doc-card-name" title={doc.name}>{doc.name}</div>
                            <div className="doc-card-time">{docTimeLabel(doc.uploaded_at)}</div>
                          </div>
                          <div className="doc-card-sub">
                            {doc.preview || `${doc.chunks} chunks indexed · ready to answer questions from this document.`}
                          </div>
                        </div>
                      </div>
                    ))}
                  </>
                )}
              </>
            )}
          </div>
        </aside>

        <div className="main-col">
          <div className="topbar">
            {messageSearchOpen ? (
              <input
                className="topbar-search"
                autoFocus
                type="text"
                placeholder="Search this conversation…"
                value={messageSearch}
                onChange={(e) => setMessageSearch(e.target.value)}
              />
            ) : (
              <div className="topbar-title">
                {chats.find((c) => c.id === currentChatId)?.title || "Document Chat"}
              </div>
            )}
            <div className="topbar-spacer"></div>
            <button
              className={`ic-btn${messageSearchOpen ? " active" : ""}`}
              title="Search this conversation"
              onClick={() => {
                setMessageSearchOpen((open) => !open);
                setMessageSearch("");
              }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            </button>
          </div>

          <main className="main">
          <div className="main-inner">
            <div
              className="chat-scroll"
              ref={scrollRef}
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleChatDrop}
            >
              {messages.length === 0 && (
                <label className="chat-empty">
                  <input
                    type="file"
                    multiple
                    accept=".txt,.pdf,.docx,.xlsx,.csv"
                    onChange={(e) => handleAttach(e.target.files)}
                  />
                  <div className="chat-empty-card">
                    <div className="chat-empty-icon">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></svg>
                    </div>
                    <p className="chat-empty-title">Upload a document to get started</p>
                    <p className="chat-empty-sub">Drop a file here, or click to browse.</p>
                    <p className="chat-empty-note">
                      <span className="chat-empty-note-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="10" rx="3"/><path d="M7 11V8a5 5 0 0 1 10 0v3"/><circle cx="12" cy="16" r="1.5"/></svg>
                      </span>
                      <span>This project is for demo purposes only, your uploaded documents and chats will not be saved.</span>
                    </p>
                  </div>
                </label>
              )}
              <div className="chat-scroll-inner">
                {messageSearch && visibleMessages.length === 0 && (
                  <p className="sb-caption" style={{ textAlign: "center", marginTop: "2rem" }}>
                    No messages match "{messageSearch}"
                  </p>
                )}
                {visibleMessages.map((m, i) => <Message message={m} key={i} />)}
              </div>
            </div>

            <div className="chat-input-bar">
              <form className="chat-input" onSubmit={handleSubmit}>
                {attachments.length > 0 && (
                  <div className="chat-attachments">
                    {attachments.map((a) => (
                      <div className="chat-attachment-chip" key={a.name}>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/></svg>
                        <span>{a.name}</span>
                        {a.status === "uploading" ? (
                          <span className="chat-attachment-spinner" />
                        ) : (
                          <button type="button" onClick={() => removeAttachment(a.name)} title="Remove">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                <div className="chat-input-row">
                  <label className="wand" title="Upload documents">
                    <input
                      type="file"
                      multiple
                      accept=".txt,.pdf,.docx,.xlsx,.csv"
                      onChange={(e) => handleAttach(e.target.files)}
                    />
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                  </label>
                  <textarea
                    rows={1}
                    placeholder="Upload documents and ask questions"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSubmit(e);
                      }
                    }}
                  />
                  <button className="send-btn" type="submit" disabled={(!question.trim() && attachments.length === 0) || sending}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                  </button>
                </div>
              </form>
            </div>
          </div>
          </main>
        </div>
      </div>
    </>
  );
}
