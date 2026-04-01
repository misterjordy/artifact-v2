/* arti chat widget — Alpine.js component for persistent floating chat. */

function getCsrfToken() {
  var match = document.cookie.match(/csrf_token=([^;]+)/);
  return match ? match[1] : "";
}

function artiChat() {
  return {
    /* ── state ─────────────────────────────────────────── */
    sessions: [],
    activeChat: null,
    newChatStep: null,
    streaming: false,
    inputText: "",
    scrolledUp: false,
    confirmingClose: false,

    /* setup flow state */
    programs: [],
    selectedProgram: null,
    constraintNodes: [],
    constraintNodeUids: [],
    selectedMode: "efficient",
    factFilter: "published",
    tokenEstimate: null,
    setupLoading: false,

    /* current chat state */
    messages: [],
    sessionTokens: 0,

    /* ── lifecycle ─────────────────────────────────────── */

    async init() {
      await this.loadSessions();
      var stored = sessionStorage.getItem("arti-active-chat");
      if (stored) {
        var found = this.sessions.find(function (s) { return s.chat_uid === stored; });
        if (found) {
          await this.openChat(stored);
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
      this.messages = [];
      this.constraintNodes = [];
      this.constraintNodeUids = [];
      this.selectedProgram = null;
      this.selectedMode = "efficient";
      this.factFilter = "published";
      this.tokenEstimate = null;
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

    /* constraint drag-drop */
    handleConstraintDrop(event) {
      event.currentTarget.classList.remove("dnd-drag-over");
      var uid = event.dataTransfer.getData("text/plain");
      var title = event.dataTransfer.getData("text/x-node-title") || uid;
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
      this.newChatStep = "mode";
    },

    confirmConstraints() {
      this.newChatStep = "mode";
    },

    async selectMode(mode) {
      this.selectedMode = mode;
      this.setupLoading = true;

      /* estimate tokens */
      var params = "program_node_uid=" + this.selectedProgram.node_uid +
        "&fact_filter=" + this.factFilter;
      if (this.constraintNodeUids.length > 0) {
        params += "&constraint_node_uids=" + this.constraintNodeUids.join(",");
      }
      try {
        var resp = await fetch("/api/v1/ai/chat/estimate?" + params);
        if (resp.ok) { this.tokenEstimate = await resp.json(); }
      } catch (e) { /* silent */ }

      /* create session */
      try {
        var body = {
          program_node_uid: this.selectedProgram.node_uid,
          mode: this.selectedMode,
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
          sessionStorage.setItem("arti-active-chat", session.chat_uid);
        }
      } catch (e) { /* silent */ }
      this.setupLoading = false;
    },

    /* ── open / minimize / close ───────────────────────── */

    async openChat(chatUid) {
      this.activeChat = chatUid;
      this.newChatStep = null;
      this.confirmingClose = false;
      sessionStorage.setItem("arti-active-chat", chatUid);
      await this.loadMessages(chatUid);
      var session = this.currentSession;
      if (session) {
        this.factFilter = session.fact_filter;
        this.sessionTokens = session.total_input_tokens + session.total_output_tokens;
      }
      this.$nextTick(function () { this.scrollToBottom(); }.bind(this));
    },

    minimizeChat() {
      this.activeChat = null;
      sessionStorage.removeItem("arti-active-chat");
    },

    promptClose() {
      this.confirmingClose = true;
    },

    cancelClose() {
      this.confirmingClose = false;
    },

    async closeChat() {
      var uid = this.activeChat;
      if (!uid || uid === "__new__") {
        this.activeChat = null;
        this.newChatStep = null;
        this.confirmingClose = false;
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
      this.activeChat = null;
      this.messages = [];
      this.confirmingClose = false;
      sessionStorage.removeItem("arti-active-chat");
    },

    /* ── messages ──────────────────────────────────────── */

    async loadMessages(chatUid) {
      try {
        var resp = await fetch("/api/v1/ai/chat/" + chatUid + "/messages");
        if (resp.ok) { this.messages = await resp.json(); }
      } catch (e) { /* silent */ }
    },

    async sendMessage() {
      var text = this.inputText.trim();
      if (!text || this.streaming) return;
      this.inputText = "";
      this.streaming = true;

      /* optimistic user message */
      this.messages.push({
        message_uid: "pending-" + Date.now(),
        role: "user",
        content: text,
        input_tokens: 0,
        output_tokens: 0,
        facts_loaded: 0,
        created_at: new Date().toISOString(),
      });
      this.scrollToBottom();

      /* placeholder for arti response */
      var artiMsg = {
        message_uid: "streaming-" + Date.now(),
        role: "assistant",
        content: "",
        input_tokens: 0,
        output_tokens: 0,
        facts_loaded: 0,
        created_at: new Date().toISOString(),
      };
      this.messages.push(artiMsg);
      var artiIndex = this.messages.length - 1;

      try {
        var resp = await fetch("/api/v1/ai/chat/" + this.activeChat + "/send", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": getCsrfToken(),
          },
          body: JSON.stringify({ content: text }),
        });

        if (!resp.ok) {
          this.messages[artiIndex].content = "Error: could not get a response.";
          this.streaming = false;
          return;
        }

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
                this.messages[artiIndex].content += evt.chunk;
                if (!this.scrolledUp) this.scrollToBottom();
              }
              if (evt.replace) {
                this.messages[artiIndex].content = evt.replace;
              }
              if (evt.done) {
                this.sessionTokens = evt.session_total_tokens || this.sessionTokens;
              }
            } catch (e) { /* skip unparseable */ }
          }
        }
      } catch (e) {
        this.messages[artiIndex].content = "Connection error. Please try again.";
      }

      this.streaming = false;
      /* reload full messages + sessions to sync server state */
      await this.loadMessages(this.activeChat);
      await this.loadSessions();
      var session = this.currentSession;
      if (session) {
        this.sessionTokens = session.total_input_tokens + session.total_output_tokens;
      }
    },

    /* ── toggle fact filter ────────────────────────────── */

    async toggleFilter() {
      var newFilter = this.factFilter === "published" ? "signed" : "published";
      if (!this.activeChat || this.activeChat === "__new__") {
        this.factFilter = newFilter;
        return;
      }
      try {
        await fetch("/api/v1/ai/chat/sessions/" + this.activeChat + "/filter", {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": getCsrfToken(),
          },
          body: JSON.stringify({ fact_filter: newFilter }),
        });
        this.factFilter = newFilter;
        /* add system-style notification */
        this.messages.push({
          message_uid: "sys-" + Date.now(),
          role: "system",
          content: "Switched to " + newFilter + " facts.",
          input_tokens: 0,
          output_tokens: 0,
          facts_loaded: 0,
          created_at: new Date().toISOString(),
        });
        this.scrollToBottom();
      } catch (e) { /* silent */ }
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
