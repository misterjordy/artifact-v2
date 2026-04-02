/* arti chat widget — Alpine.js component for persistent floating chat. */

function getCsrfToken() {
  var match = document.cookie.match(/csrf_token=([^;]+)/);
  return match ? match[1] : "";
}

// formatTokens() is in /static/js/token-counter.js (loaded globally)

function artiChat() {
  return {
    /* ── state ─────────────────────────────────────────── */
    sessions: [],
    activeChat: null,
    newChatStep: null,
    streaming: false,
    inputText: "",
    scrolledUp: false,
    errorMessage: null,
    skipTransition: false,

    /* setup flow state */
    programs: [],
    selectedProgram: null,
    constraintNodes: [],
    constraintNodeUids: [],
    factFilter: "published",
    setupLoading: false,

    /* current chat state */
    messages: [],
    sessionTokens: 0,
    scopeFactCount: 0,
    fullCorpusTokenEstimate: 0,
    messageCache: {},

    /* ── lifecycle ─────────────────────────────────────── */

    async init() {
      await this.loadSessions();
      var stored = sessionStorage.getItem("arti-active-chat");
      if (stored) {
        var found = this.sessions.find(function (s) { return s.chat_uid === stored; });
        if (found) {
          /* skip enter animation on page restore */
          this.skipTransition = true;
          await this.openChat(stored);
          var self = this;
          this.$nextTick(function () { self.skipTransition = false; });
        }
      }
    },

    /* ── session management ────────────────────────────── */

    async loadSessions() {
      try {
        var resp = await fetch("/api/v1/ai/chat/sessions");
        if (resp.ok) { this.sessions = await resp.json(); }
      } catch (e) { /* silent */ }
    },

    get minimizedSessions() {
      var active = this.activeChat;
      return this.sessions.filter(function (s) { return s.chat_uid !== active; });
    },

    get currentSession() {
      var active = this.activeChat;
      return this.sessions.find(function (s) { return s.chat_uid === active; }) || null;
    },

    abbreviation(session) {
      if (!session || !session.program_name) return "arti";
      var parts = session.program_name.split(/[\s-]+/);
      if (parts.length >= 2) return parts[0].substring(0, 1) + parts[1].substring(0, 2);
      return session.program_name.substring(0, 3);
    },

    /* ── new chat flow ─────────────────────────────────── */

    async startNewChat() {
      this.activeChat = "__new__";
      this.newChatStep = "program";
      this.errorMessage = null;
      this.messages = [];
      this.constraintNodes = [];
      this.constraintNodeUids = [];
      this.selectedProgram = null;
      this.factFilter = "published";
      this.scopeFactCount = 0;
      this.fullCorpusTokenEstimate = 0;
      sessionStorage.setItem("arti-active-chat", "__new__");
      await this.loadPrograms();
    },

    async loadPrograms() {
      try {
        var resp = await fetch("/api/v1/ai/context");
        if (resp.ok) {
          var data = await resp.json();
          this.programs = data.programs || [];
          if (this.programs.length === 1) {
            this.selectProgram(this.programs[0]);
          }
        }
      } catch (e) { /* silent */ }
    },

    selectProgram(prog) {
      this.selectedProgram = prog;
      this.newChatStep = "constraint";
    },

    /* constraint drag-drop — supports both import.js keys and browse_dnd.js keys */
    handleConstraintDrop(event) {
      event.currentTarget.classList.remove("dnd-drag-over");
      var uid = event.dataTransfer.getData("text/plain")
             || event.dataTransfer.getData("text/x-entity-uid");
      var title = event.dataTransfer.getData("text/x-node-title")
               || event.dataTransfer.getData("text/x-entity-label")
               || uid;
      /* ignore fact drags from browse — only accept node drags */
      var moveType = event.dataTransfer.getData("text/x-move-type");
      if (moveType === "fact") return;
      if (uid && this.constraintNodeUids.indexOf(uid) === -1) {
        this.constraintNodeUids.push(uid);
        this.constraintNodes.push({ uid: uid, title: title });
      }
    },

    removeConstraint(index) {
      this.constraintNodeUids.splice(index, 1);
      this.constraintNodes.splice(index, 1);
    },

    skipConstraints() {
      this.createSession();
    },

    confirmConstraints() {
      this.createSession();
    },

    async createSession() {
      this.setupLoading = true;

      /* estimate scope tokens */
      var params = "program_node_uid=" + this.selectedProgram.node_uid +
        "&fact_filter=" + this.factFilter;
      if (this.constraintNodeUids.length > 0) {
        params += "&constraint_node_uids=" + this.constraintNodeUids.join(",");
      }
      try {
        var resp = await fetch("/api/v1/ai/chat/estimate?" + params);
        if (resp.ok) {
          var est = await resp.json();
          this.scopeFactCount = est.fact_count || 0;
          this.fullCorpusTokenEstimate = est.full_corpus_token_estimate || est.estimated_tokens || 0;
        }
      } catch (e) { /* silent */ }

      /* create session */
      try {
        var body = {
          program_node_uid: this.selectedProgram.node_uid,
          fact_filter: this.factFilter,
        };
        if (this.constraintNodeUids.length > 0) {
          body.constraint_node_uids = this.constraintNodeUids;
        }
        var resp2 = await fetch("/api/v1/ai/chat/sessions", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": getCsrfToken(),
          },
          body: JSON.stringify(body),
        });
        if (resp2.ok) {
          var session = await resp2.json();
          this.sessions.push(session);
          this.activeChat = session.chat_uid;
          this.newChatStep = null;
          this.messages = [];
          this.sessionTokens = 0;
          this.errorMessage = null;
          sessionStorage.setItem("arti-active-chat", session.chat_uid);
        } else if (resp2.status === 409) {
          this.errorMessage = "session-limit";
          this.newChatStep = null;
        } else {
          this.errorMessage = "create-failed";
          this.newChatStep = null;
        }
      } catch (e) { this.errorMessage = "create-failed"; this.newChatStep = null; }
      this.setupLoading = false;
    },

    /* ── open / minimize / close ───────────────────────── */

    async openChat(chatUid) {
      /* cache messages from current chat before switching */
      if (this.activeChat && this.activeChat !== "__new__" && this.messages.length > 0) {
        this.messageCache[this.activeChat] = this.messages.slice();
      }
      this.activeChat = chatUid;
      this.newChatStep = null;
      this.errorMessage = null;
      sessionStorage.setItem("arti-active-chat", chatUid);
      /* restore from cache for instant swap, then refresh from server */
      if (this.messageCache[chatUid]) {
        this.messages = this.messageCache[chatUid];
      } else {
        this.messages = [];
      }
      await this.loadMessages(chatUid);
      var session = this.currentSession;
      if (session) {
        this.factFilter = session.fact_filter;
        this.sessionTokens = session.total_input_tokens + session.total_output_tokens;
      }
      this.$nextTick(function () { this.scrollToBottom(); }.bind(this));
    },

    minimizeChat() {
      if (this.activeChat && this.activeChat !== "__new__" && this.messages.length > 0) {
        this.messageCache[this.activeChat] = this.messages.slice();
      }
      this.activeChat = null;
      sessionStorage.removeItem("arti-active-chat");
    },

    async closeChat() {
      var uid = this.activeChat;
      if (!uid || uid === "__new__") {
        this.activeChat = null;
        this.newChatStep = null;
        sessionStorage.removeItem("arti-active-chat");
        return;
      }
      try {
        await fetch("/api/v1/ai/chat/sessions/" + uid, {
          method: "DELETE",
          headers: { "X-CSRF-Token": getCsrfToken() },
        });
      } catch (e) { /* silent */ }
      this.sessions = this.sessions.filter(function (s) { return s.chat_uid !== uid; });
      delete this.messageCache[uid];
      this.activeChat = null;
      this.messages = [];
      sessionStorage.removeItem("arti-active-chat");
    },

    /* ── messages ──────────────────────────────────────── */

    async loadMessages(chatUid) {
      try {
        var resp = await fetch("/api/v1/ai/chat/" + chatUid + "/messages");
        if (resp.ok) { this.messages = await resp.json(); }
      } catch (e) { /* silent */ }
    },

    async sendMessage(fullCorpus) {
      var text = this.inputText.trim();
      if (!text || this.streaming) return;
      this.inputText = "";
      await this._sendText(text, !!fullCorpus);
    },

    async resendWithFullCorpus(msg) {
      /* Find the user message that preceded this assistant message */
      var idx = this.messages.indexOf(msg);
      if (idx <= 0) return;
      var userMsg = null;
      for (var j = idx - 1; j >= 0; j--) {
        if (this.messages[j].role === "user") {
          userMsg = this.messages[j];
          break;
        }
      }
      if (!userMsg) return;
      /* Remove old assistant response and resend */
      this.messages.splice(idx, 1);
      await this._sendText(userMsg.content, true);
    },

    async _sendText(text, fullCorpus) {
      this.streaming = true;

      /* optimistic user message (only if not resending) */
      var lastMsg = this.messages[this.messages.length - 1];
      if (!lastMsg || lastMsg.role !== "user" || lastMsg.content !== text) {
        this.messages.push({
          message_uid: "pending-" + Date.now(),
          role: "user",
          content: text,
          input_tokens: 0, output_tokens: 0, facts_loaded: 0,
          created_at: new Date().toISOString(),
        });
      }
      this.scrollToBottom();

      /* placeholder for arti response */
      var artiMsg = {
        message_uid: "streaming-" + Date.now(),
        role: "assistant",
        content: "",
        input_tokens: 0, output_tokens: 0, facts_loaded: 0,
        created_at: new Date().toISOString(),
        _fullCorpus: fullCorpus || false,
      };
      this.messages.push(artiMsg);
      var chatUid = this.activeChat;

      try {
        var resp = await fetch("/api/v1/ai/chat/" + chatUid + "/send", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": getCsrfToken(),
          },
          body: JSON.stringify({ content: text, full_corpus: !!fullCorpus }),
        });

        if (!resp.ok) {
          var errText = "";
          try { var errBody = await resp.json(); errText = errBody.detail || ""; } catch (e) { /* */ }
          if (resp.status === 400 && errText.indexOf("No AI API key") !== -1) {
            artiMsg.content = "No AI API key configured. Add one in Settings.";
            this.errorMessage = "no-ai-key";
          } else if (resp.status === 429) {
            artiMsg.content = "Rate limit reached. Wait a moment and try again.";
          } else {
            artiMsg.content = "Error: " + (errText || "could not get a response.");
          }
          artiMsg._error = true;
          this.streaming = false;
          return;
        }

        var contentType = resp.headers.get("Content-Type") || "";

        if (contentType.indexOf("application/json") !== -1) {
          /* Static frame (no API key) */
          var data = await resp.json();
          var frame = data.data || data;
          artiMsg._staticFrame = true;
          artiMsg._frameMessage = frame.message || "";
          artiMsg._frameFacts = frame.facts || [];
          artiMsg._frameAction = frame.action || { label: "Add AI key in Settings", url: "/settings#ai-key" };
          artiMsg.content = frame.message || "";
          this.streaming = false;
          this.scrollToBottom();
          return;
        }

        /* SSE streaming */
        var reader = resp.body.getReader();
        var decoder = new TextDecoder();
        var buffer = "";

        while (true) {
          var result = await reader.read();
          if (result.done) break;
          buffer += decoder.decode(result.value, { stream: true });

          var lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            if (!line.startsWith("data: ")) continue;
            var payload = line.substring(6).trim();
            if (!payload || payload === "[DONE]") continue;

            try {
              var evt = JSON.parse(payload);
              if (evt.chunk) {
                artiMsg.content += evt.chunk;
                if (!this.scrolledUp) this.scrollToBottom();
              }
              if (evt.replace) {
                artiMsg.content = evt.replace;
              }
              if (evt.done) {
                this.sessionTokens = evt.session_total_tokens || this.sessionTokens;
                if (evt.scope_fact_count) this.scopeFactCount = evt.scope_fact_count;
                if (evt.full_corpus_token_estimate) this.fullCorpusTokenEstimate = evt.full_corpus_token_estimate;
                if (evt.input_tokens === 0 && evt.output_tokens === 0) {
                  artiMsg._error = true;
                }
              }
            } catch (e) { /* skip unparseable */ }
          }
        }
      } catch (e) {
        artiMsg.content = "Connection error. Please try again.";
        artiMsg._error = true;
      }

      this.streaming = false;
      if (artiMsg.content && !artiMsg._error) {
        await this.loadMessages(this.activeChat);
        await this.loadSessions();
        var session = this.currentSession;
        if (session) {
          this.sessionTokens = session.total_input_tokens + session.total_output_tokens;
        }
        document.dispatchEvent(new CustomEvent("ai-usage-changed"));
      }
    },

    /* ── toggle fact filter ────────────────────────────── */

    async toggleFilter() {
      var oldFilter = this.factFilter;
      var newFilter = oldFilter === "published" ? "signed" : "published";
      /* optimistic update */
      this.factFilter = newFilter;
      if (!this.activeChat || this.activeChat === "__new__") return;
      try {
        var resp = await fetch("/api/v1/ai/chat/sessions/" + this.activeChat + "/filter", {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": getCsrfToken(),
          },
          body: JSON.stringify({ fact_filter: newFilter }),
        });
        if (!resp.ok) { this.factFilter = oldFilter; return; }
        /* server wiped messages — clear local state to match */
        this.messages = [{
          message_uid: "sys-" + Date.now(),
          role: "system",
          content: "Switched to " + newFilter + " facts. Chat history cleared.",
          input_tokens: 0,
          output_tokens: 0,
          facts_loaded: 0,
          created_at: new Date().toISOString(),
        }];
        this.sessionTokens = 0;
        this.scrollToBottom();
      } catch (e) { this.factFilter = oldFilter; }
    },

    /* ── scroll management ─────────────────────────────── */

    handleScroll(event) {
      var el = event.target;
      var atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
      this.scrolledUp = !atBottom;
    },

    scrollToBottom() {
      var self = this;
      this.$nextTick(function () {
        var el = self.$refs.msgArea;
        if (el) { el.scrollTop = el.scrollHeight; }
        self.scrolledUp = false;
      });
    },

    /* ── ticker ────────────────────────────────────────── */

    tickerText() {
      var s = this.currentSession;
      if (!s) return "arti";
      var text = "arti > " + s.program_name;
      if (s.constraint_names && s.constraint_names.length > 0) {
        text += " > " + s.constraint_names.join(", ");
      }
      return text;
    },

    initTicker() {
      var self = this;
      this.$nextTick(function () {
        var inner = self.$refs.tickerInner;
        var outer = self.$refs.tickerOuter;
        if (!inner || !outer) return;
        var overflow = inner.scrollWidth - outer.clientWidth;
        if (overflow > 0) {
          inner.style.setProperty("--ticker-dist", "-" + overflow + "px");
          inner.classList.add("arti-ticker");
        } else {
          inner.classList.remove("arti-ticker");
        }
      });
    },

    /* ── keyboard ──────────────────────────────────────── */

    handleKey(event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        this.sendMessage();
      }
    },
  };
}
