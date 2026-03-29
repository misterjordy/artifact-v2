"use strict";

function settingsApp() {
  var csrfToken = document.cookie
    .split("; ")
    .find(function (c) {
      return c.startsWith("csrf_token=");
    });
  csrfToken = csrfToken ? csrfToken.split("=")[1] : "";

  return {
    keys: [],
    form: { provider: "openai", api_key: "", model_override: "" },
    saveMsg: "",
    saveErr: "",

    async init() {
      await this.loadKeys();
    },

    async loadKeys() {
      var r = await fetch("/api/v1/ai/keys", { credentials: "same-origin" });
      if (r.ok) this.keys = await r.json();
    },

    async saveKey() {
      this.saveMsg = "";
      this.saveErr = "";
      var body = {
        provider: this.form.provider,
        api_key: this.form.api_key,
      };
      if (this.form.model_override) body.model_override = this.form.model_override;
      var r = await fetch("/api/v1/ai/keys", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        credentials: "same-origin",
        body: JSON.stringify(body),
      });
      if (r.ok) {
        this.saveMsg = "Key saved!";
        this.form.api_key = "";
        this.form.model_override = "";
        await this.loadKeys();
      } else {
        var d = await r.json();
        this.saveErr = d.detail || "Failed to save";
      }
    },

    async deleteKey(provider) {
      var r = await fetch("/api/v1/ai/keys/" + provider, {
        method: "DELETE",
        headers: { "X-CSRF-Token": csrfToken },
        credentials: "same-origin",
      });
      if (r.ok || r.status === 204) await this.loadKeys();
    },
  };
}
