"use strict";

/* Token counter — sidebar usage display. Loaded globally via base.html. */

function formatTokens(n) {
  if (n == null || n === 0) return "0";
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return String(n);
}

function tokenCounter() {
  return {
    totalTokens: 0,
    callCount: 0,
    byAction: {},
    byProvider: [],
    showBreakdown: false,

    init() {
      this.load();
      document.addEventListener("ai-usage-changed", this.load.bind(this));
    },

    async load() {
      try {
        var resp = await fetch("/api/v1/ai/usage/summary");
        if (!resp.ok) return;
        var data = await resp.json();
        this.totalTokens = data.data.total_tokens || 0;
        this.callCount = data.data.call_count || 0;
        this.byAction = data.data.by_action || {};
        this.byProvider = data.data.by_provider || [];
      } catch (e) { /* silent */ }
    },

    formatTokens: formatTokens,

    formatAction(action) {
      var labels = {
        "chat": "Arti Chat",
        "ai_complete": "AI Call",
        "smart_tags": "Smart Tags",
        "smart_tags_batch": "Smart Tags (bulk)",
        "import_classify": "Import",
        "import_conflict": "Import",
      };
      return labels[action] || action;
    },
  };
}
