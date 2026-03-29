"use strict";

function chatApp() {
  var csrfToken = document.cookie
    .split("; ")
    .find(function (c) {
      return c.startsWith("csrf_token=");
    });
  csrfToken = csrfToken ? csrfToken.split("=")[1] : "";

  return {
    messages: [],
    input: "",
    streaming: false,
    streamBuffer: "",
    errorMsg: "",
    selectedNode: "",
    programs: [],
    topics: {},
    factsLoaded: 0,
    factsTotal: 0,

    async init() {
      await this.loadContext();
      this.$refs.chatInput?.focus();
    },

    async loadContext() {
      var r = await fetch("/api/v1/ai/context", { credentials: "same-origin" });
      if (r.ok) {
        var data = await r.json();
        this.programs = data.programs;
        this.topics = data.topics;
      }
    },

    async sendMessage() {
      var msg = this.input.trim();
      if (!msg) return;
      this.errorMsg = "";
      this.messages.push({ role: "user", content: msg });
      this.input = "";
      this.streaming = true;
      this.streamBuffer = "";

      var history = this.messages
        .slice(0, -1)
        .slice(-20)
        .map(function (m) {
          return { role: m.role, content: m.content };
        });

      var body = { message: msg, history: history };
      if (this.selectedNode) body.node_uid = this.selectedNode;

      try {
        var r = await fetch("/api/v1/ai/chat/stream", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrfToken,
          },
          credentials: "same-origin",
          body: JSON.stringify(body),
        });

        if (!r.ok) {
          var d = await r.json();
          this.errorMsg = d.detail || "Chat request failed";
          this.streaming = false;
          return;
        }

        var reader = r.body.getReader();
        var decoder = new TextDecoder();
        var buf = "";

        while (true) {
          var result = await reader.read();
          if (result.done) break;
          buf += decoder.decode(result.value, { stream: true });
          var lines = buf.split("\n");
          buf = lines.pop() || "";
          for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            if (!line.startsWith("data: ")) continue;
            var payload = line.slice(6);
            if (payload === "[DONE]") break;
            try {
              var evt = JSON.parse(payload);
              if (evt.type === "meta") {
                this.factsLoaded = evt.data.facts_loaded;
                this.factsTotal = evt.data.facts_total;
              } else if (evt.type === "chunk") {
                this.streamBuffer += evt.data;
              } else if (evt.type === "replace") {
                this.streamBuffer = evt.data;
              }
            } catch (_e) {}
          }
          this.scrollToBottom();
        }

        this.messages.push({ role: "assistant", content: this.streamBuffer });
      } catch (_e) {
        this.errorMsg = "Network error \u2014 check your connection.";
      }
      this.streaming = false;
      this.streamBuffer = "";
      this.scrollToBottom();
    },

    scrollToBottom() {
      this.$nextTick(function () {
        var el = document.getElementById("chat-messages");
        if (el) el.scrollTop = el.scrollHeight;
      });
    },
  };
}
