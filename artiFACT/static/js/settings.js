"use strict";

function themeToggle() {
  return {
    currentTheme: localStorage.getItem("artifact-theme") || "eyecare",
    setTheme: function (theme) {
      this.currentTheme = theme;
      document.documentElement.classList.remove("eyecare", "dark", "default");
      document.documentElement.classList.add(theme);
      localStorage.setItem("artifact-theme", theme);
    },
  };
}

/* Font-size slider: piecewise linear mapping
   Slider 0 → 75%,  Slider 30 → 100% (default),  Slider 100 → 150%  */
function _sliderToPercent(v) {
  if (v <= 30) return 75 + (v / 30) * 25;            // 75–100%
  return 100 + ((v - 30) / 70) * 50;                 // 100–150%
}
function _percentToSlider(p) {
  if (p <= 100) return ((p - 75) / 25) * 30;
  return 30 + ((p - 100) / 50) * 70;
}
function _applyFontScale(pct) {
  document.documentElement.style.setProperty("--font-scale", pct / 100);
}

/* Restore font scale on every page load */
(function () {
  var stored = localStorage.getItem("artifact-font-scale");
  if (stored) _applyFontScale(Number(stored));
})();

function fontSizeSlider() {
  var stored = localStorage.getItem("artifact-font-scale");
  var pct = stored ? Number(stored) : 100;
  return {
    sliderVal: Math.round(_percentToSlider(pct)),
    displayPct: Math.round(pct),
    update: function () {
      var p = Math.round(_sliderToPercent(this.sliderVal));
      this.displayPct = p;
      _applyFontScale(p);
      localStorage.setItem("artifact-font-scale", String(p));
    },
    reset: function () {
      this.sliderVal = 30;
      this.displayPct = 100;
      _applyFontScale(100);
      localStorage.setItem("artifact-font-scale", "100");
    },
  };
}

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
