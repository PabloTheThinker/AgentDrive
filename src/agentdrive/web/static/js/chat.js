// chat.js — substrate-grounded chat sidebar client
(() => {
  const sidebar = document.getElementById("chatSidebar");
  if (!sidebar) return;

  const els = {
    thread: document.getElementById("chatThread"),
    input: document.getElementById("chatInput"),
    send: document.getElementById("chatSend"),
    model: document.getElementById("chatModel"),
    status: document.getElementById("chatStatus"),
    collapse: document.getElementById("chatCollapse"),
    newThread: document.getElementById("chatNewThread"),
    substrateToggle: document.getElementById("chatSubstrateToggle"),
    agentName: document.getElementById("chatAgentName"),
    agentRole: document.getElementById("chatAgentRole"),
  };

  let threadId = localStorage.getItem("agentdrive.chat.threadId") || "";
  let useSubstrate = true;
  let agents = [];
  let activeAgentId = localStorage.getItem("agentdrive.chat.agentId") || "";

  const renderAgentHeader = () => {
    if (!els.agentName) return;
    if (!agents.length) {
      els.agentName.textContent = "Agent Drive";
      els.agentRole.textContent = "· no agents — add one under ~/.agentdrive/agents/";
      return;
    }
    const active = agents.find((a) => a.agent_id === activeAgentId) || agents[0];
    activeAgentId = active.agent_id;
    els.agentName.textContent = active.label;
    els.agentRole.textContent =
      agents.length > 1
        ? `· ${agents.length} agents · click to switch`
        : "· your agent";
    if (els.input) {
      els.input.placeholder = `Ask ${active.label} about the substrate…  (⌘+↵ to send)`;
    }
    for (const who of els.thread.querySelectorAll(".chat-msg-agent .chat-msg-who")) {
      who.textContent = active.label;
    }
  };

  const loadAgents = async () => {
    try {
      const resp = await fetch("/api/chat/agents");
      if (!resp.ok) return;
      const data = await resp.json();
      agents = data.agents || [];
      renderAgentHeader();
    } catch {
      /* offline-safe */
    }
  };

  const switchAgent = () => {
    if (agents.length < 2) return;
    const idx = agents.findIndex((a) => a.agent_id === activeAgentId);
    const next = agents[(idx + 1) % agents.length];
    activeAgentId = next.agent_id;
    localStorage.setItem("agentdrive.chat.agentId", activeAgentId);
    // New agent → new thread, so the system prompt is the new agent's
    threadId = "";
    localStorage.removeItem("agentdrive.chat.threadId");
    els.thread.innerHTML =
      '<div class="chat-empty">Switched to ' + activeAgentId + '. New thread.</div>';
    renderAgentHeader();
  };

  // ── helpers ──────────────────────────────────────────────────────
  const escape = (s) =>
    String(s).replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );

  const fmtCode = (text) =>
    escape(text).replace(/`([^`]+)`/g, (_, m) => `<code>${m}</code>`);

  const setStatus = (s) => {
    if (els.status) els.status.textContent = s;
  };

  const scrollThread = () => {
    els.thread.scrollTop = els.thread.scrollHeight;
  };

  const clearEmpty = () => {
    const empty = els.thread.querySelector(".chat-empty");
    if (empty) empty.remove();
  };

  const agentLabel = () => {
    if (!agents.length) return "Agent";
    const active = agents.find((a) => a.agent_id === activeAgentId) || agents[0];
    return active.label;
  };

  const appendMsg = (role, text, opts = {}) => {
    clearEmpty();
    const msg = document.createElement("div");
    msg.className = `chat-msg ${role === "assistant" ? "chat-msg-agent" : ""}`;
    const initial = role === "assistant" ? "◆" : "P";
    const who = role === "assistant" ? agentLabel() : "You";
    msg.innerHTML = `
      <div class="chat-msg-avatar">${initial}</div>
      <div class="chat-msg-body">
        <div class="chat-msg-who">${escape(who)}</div>
        <div class="chat-msg-text"></div>
        <div class="chat-msg-tools"></div>
        <div class="chat-msg-meta"></div>
      </div>
    `;
    msg.querySelector(".chat-msg-text").innerHTML = fmtCode(text || "");
    els.thread.appendChild(msg);
    scrollThread();
    return msg;
  };

  const appendToolCard = (msgEl, read) => {
    const wrap = msgEl.querySelector(".chat-msg-tools");
    const card = document.createElement("div");
    card.className = "chat-tool-card";
    const latency = read.latency_ms ? `${read.latency_ms}ms` : "—";
    card.innerHTML = `
      <div class="chat-tool-head">
        <span>↗ ${escape(read.kind)} · ${escape(read.path || "")}</span>
        <span>${latency}</span>
      </div>
      <div class="chat-tool-summary">${escape(read.summary || "")}</div>
    `;
    wrap.appendChild(card);
  };

  // ── thread management ───────────────────────────────────────────
  const ensureThread = async () => {
    if (threadId) return threadId;
    setStatus("creating thread…");
    const resp = await fetch("/api/chat/threads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: els.model.value,
        agent_id: activeAgentId,
      }),
    });
    if (!resp.ok) throw new Error(`thread create failed: ${resp.status}`);
    const data = await resp.json();
    threadId = data.thread_id;
    localStorage.setItem("agentdrive.chat.threadId", threadId);
    sidebar.dataset.threadId = threadId;
    setStatus("ready");
    return threadId;
  };

  const loadThread = async () => {
    if (!threadId) return;
    try {
      const resp = await fetch(`/api/chat/threads/${threadId}`);
      if (!resp.ok) {
        threadId = "";
        localStorage.removeItem("agentdrive.chat.threadId");
        return;
      }
      const data = await resp.json();
      // Sync the header to whichever agent this thread targets.
      if (data.agent_id) {
        activeAgentId = data.agent_id;
        localStorage.setItem("agentdrive.chat.agentId", activeAgentId);
        renderAgentHeader();
      }
      for (const m of data.messages || []) {
        const node = appendMsg(m.role, m.content);
        for (const r of m.substrate_reads || []) appendToolCard(node, r);
      }
    } catch {
      /* offline-safe */
    }
  };

  // ── send + stream ───────────────────────────────────────────────
  const send = async () => {
    const text = els.input.value.trim();
    if (!text) return;
    els.input.value = "";
    els.input.style.height = "auto";
    els.send.disabled = true;
    setStatus("sending…");

    appendMsg("user", text);
    const assistantMsg = appendMsg("assistant", "");
    const textEl = assistantMsg.querySelector(".chat-msg-text");
    const metaEl = assistantMsg.querySelector(".chat-msg-meta");
    textEl.classList.add("chat-streaming");

    let tid;
    try {
      tid = await ensureThread();
    } catch (err) {
      textEl.textContent = `[error] ${err.message}`;
      textEl.classList.remove("chat-streaming");
      els.send.disabled = false;
      setStatus("error");
      return;
    }

    let buffer = "";
    try {
      const resp = await fetch(`/api/chat/threads/${tid}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: text,
          model: els.model.value,
          use_substrate: useSubstrate,
        }),
      });
      if (!resp.ok || !resp.body) {
        textEl.textContent = `[error] HTTP ${resp.status}`;
        textEl.classList.remove("chat-streaming");
        els.send.disabled = false;
        setStatus("error");
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let pending = "";

      const processEvent = (rawEvent) => {
        const lines = rawEvent.split("\n");
        let event = "message";
        let dataStr = "";
        for (const line of lines) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
        }
        if (!dataStr) return;
        let data;
        try {
          data = JSON.parse(dataStr);
        } catch {
          return;
        }
        if (event === "substrate_read") {
          appendToolCard(assistantMsg, data);
        } else if (event === "token") {
          buffer += data.text || "";
          textEl.innerHTML = fmtCode(buffer);
          scrollThread();
        } else if (event === "done") {
          textEl.classList.remove("chat-streaming");
          metaEl.textContent = `${data.model || ""} · ${(data.substrate_reads || []).length} reads`;
          setStatus("ready");
        } else if (event === "error") {
          textEl.innerHTML = `<em>${escape(data.error || "error")}</em>`;
          textEl.classList.remove("chat-streaming");
          setStatus("error");
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        pending += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = pending.indexOf("\n\n")) !== -1) {
          const raw = pending.slice(0, idx);
          pending = pending.slice(idx + 2);
          if (raw.trim()) processEvent(raw);
        }
      }
      if (pending.trim()) processEvent(pending);
    } catch (err) {
      textEl.textContent = `[stream error] ${err.message}`;
      textEl.classList.remove("chat-streaming");
      setStatus("error");
    } finally {
      els.send.disabled = false;
    }
  };

  // ── wiring ─────────────────────────────────────────────────────
  els.send.addEventListener("click", send);
  els.input.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      send();
    }
  });
  els.input.addEventListener("input", () => {
    els.input.style.height = "auto";
    els.input.style.height = Math.min(els.input.scrollHeight, 140) + "px";
  });
  els.collapse.addEventListener("click", () => {
    sidebar.classList.toggle("collapsed");
  });
  els.newThread.addEventListener("click", () => {
    threadId = "";
    localStorage.removeItem("agentdrive.chat.threadId");
    els.thread.innerHTML =
      '<div class="chat-empty">New thread. Ask ILO about your substrate.</div>';
    setStatus("ready");
  });
  els.substrateToggle.addEventListener("click", () => {
    useSubstrate = !useSubstrate;
    els.substrateToggle.classList.toggle("chat-toggle-on", useSubstrate);
  });

  // Click the header agent name to cycle through agents
  if (els.agentName) {
    els.agentName.style.cursor = "pointer";
    els.agentName.addEventListener("click", switchAgent);
  }

  // boot
  (async () => {
    await loadAgents();
    await loadThread();
  })();
})();
