"use strict";

function getCsrfToken() {
  var match = document.cookie.match(/csrf_token=([^;]+)/);
  return match ? match[1] : "";
}

// === Fact selection / outline state ===

window._selectedFactUid = null;

window.selectFact = function (factUid, versionUid) {
  // Clear previous outline
  window.clearFactSelection();
  // Set new selection
  window._selectedFactUid = factUid;
  var row = document.querySelector('[data-fact-uid="' + factUid + '"]');
  if (row) {
    row.classList.add("ring-2", "ring-[var(--color-accent)]", "bg-[var(--color-accent)]/5");
  }
  // Open right pane with fact history
  window.openRightPane("Fact History");
};

window.clearFactSelection = function () {
  if (window._selectedFactUid) {
    var prev = document.querySelector('[data-fact-uid="' + window._selectedFactUid + '"]');
    if (prev) {
      prev.classList.remove("ring-2", "ring-[var(--color-accent)]", "bg-[var(--color-accent)]/5");
    }
  }
  window._selectedFactUid = null;
};

// === Alpine component: browse search with program grouping ===

function browseSearch() {
  return {
    searchQuery: "",
    searchResults: { programs: [], total: 0 },
    searchOpen: false,
    searching: false,

    async doSearch() {
      var q = this.searchQuery.trim();
      if (q.length < 2) {
        this.searchResults = { programs: [], total: 0 };
        this.searchOpen = false;
        return;
      }
      this.searchOpen = true;
      this.searching = true;
      try {
        var resp = await fetch("/api/v1/search?q=" + encodeURIComponent(q));
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        var json = await resp.json();
        this.searchResults = json.data || { programs: [], total: 0 };
      } catch (e) {
        this.searchResults = { programs: [], total: 0 };
      } finally {
        this.searching = false;
      }
    },

    clearSearch() {
      this.searchQuery = "";
      this.searchResults = { programs: [], total: 0 };
      this.searchOpen = false;
    },

    onEscape() {
      if (this.searchOpen) {
        this.clearSearch();
        var input = document.getElementById("sidebar-search-input");
        if (input) input.blur();
      }
    },

    async navigateToFact(result) {
      // 1. Load the fact's node in the center pane
      var promise = new Promise(function (resolve) {
        var handler = function () {
          document.body.removeEventListener("htmx:afterSettle", handler);
          resolve();
        };
        document.body.addEventListener("htmx:afterSettle", handler);
        // Timeout fallback in case HTMX doesn't fire settle
        setTimeout(resolve, 2000);
      });

      htmx.ajax("GET", "/partials/browse/" + result.node_uid, {
        target: "#center-pane",
        swap: "innerHTML",
      });

      await promise;

      // 2. Find the fact row and scroll to it
      var factRow = document.querySelector('[data-fact-uid="' + result.fact_uid + '"]');
      if (factRow) {
        factRow.scrollIntoView({ behavior: "smooth", block: "center" });
      }

      // 3. Select the fact (outline + right pane)
      window.selectFact(result.fact_uid, result.version_uid);

      // 4. Load the right pane history
      htmx.ajax("GET", "/partials/fact-history/" + result.fact_uid, {
        target: "#right-pane-content",
        swap: "innerHTML",
      });

      // 5. Search stays open — do NOT close
    },
  };
}

document.addEventListener("DOMContentLoaded", function () {
  // Inject CSRF token into every HTMX state-changing request
  document.body.addEventListener("htmx:configRequest", function (evt) {
    var token = getCsrfToken();
    if (token) {
      evt.detail.headers["X-CSRF-Token"] = token;
    }
  });

  // Listen for custom triggers from successful form submissions
  document.body.addEventListener("refreshTree", function () {
    htmx.trigger("#tree-container", "refreshTree");
  });

  document.body.addEventListener("refreshNode", function (evt) {
    var nodeUid = evt.detail && evt.detail.nodeUid;
    if (nodeUid) {
      htmx.ajax("GET", "/partials/browse/" + nodeUid, { target: "#center-pane", swap: "innerHTML" });
    }
  });

  // Clear modal when clicking backdrop (handled by Alpine, but also on htmx settle)
  document.body.addEventListener("closeModal", function () {
    var modal = document.getElementById("modal");
    if (modal) {
      modal.innerHTML = "";
    }
  });
});

// === Smart Tags — utilities ===

function _showToast(msg, type) {
  var el = document.createElement("div");
  el.className = "fixed bottom-4 right-4 z-50 px-4 py-2 rounded shadow-lg text-sm max-w-sm " +
    (type === "error" ? "bg-red-600 text-white"
      : type === "warn" ? "bg-yellow-600 text-white"
      : "bg-green-600 text-white");
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(function () { el.remove(); }, 4000);
}

// === Smart Tags — lightbulb generate ===

window.generateSmartTags = function (btn, factUid, versionUid) {
  if (btn.disabled) return;
  btn.disabled = true;
  var svg = btn.querySelector("svg");
  if (svg) svg.classList.add("animate-pulse");

  fetch("/api/v1/facts/" + factUid + "/versions/" + versionUid + "/smart-tags/generate", {
    method: "POST",
    headers: { "X-CSRF-Token": getCsrfToken() },
  })
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (data) {
      var tags = data.data.tags;
      btn.classList.remove("text-[var(--color-text-muted)]");
      btn.classList.add("text-yellow-400");
      var row = btn.closest("[data-fact-uid]");
      if (row) row.dataset.smartTags = JSON.stringify(tags);
      _showToast("Generated " + tags.length + " smart tags");
      document.dispatchEvent(new CustomEvent("ai-usage-changed"));
    })
    .catch(function (e) {
      if (e.message.indexOf("400") !== -1) {
        _showToast("AI key required. Add one in Settings → AI Key.", "error");
      } else {
        _showToast("Failed to generate tags", "error");
      }
    })
    .finally(function () {
      btn.disabled = false;
      if (svg) svg.classList.remove("animate-pulse");
    });
};

// === Make All Smart — sub-button pane Alpine component ===

function makeAllSmartPane(nodeUid) {
  return {
    nodeUid: nodeUid,
    expanded: false,
    loading: false,
    mode: null,
    progressTagged: 0,
    progressTotal: 0,
    est_nd: { fact_count: 0, estimated_total_tokens: 0 },
    est_repl: { fact_count: 0, estimated_total_tokens: 0 },

    async toggle() {
      if (this.expanded) { this.expanded = false; return; }
      await this.fetchEstimates();
      this.expanded = true;
    },

    async fetchEstimates() {
      try {
        var base = "/api/v1/nodes/" + this.nodeUid + "/smart-tags/estimate";
        var r1 = await fetch(base + "?replace=false");
        var r2 = await fetch(base + "?replace=true");
        if (r1.ok) this.est_nd = (await r1.json()).data;
        if (r2.ok) this.est_repl = (await r2.json()).data;
      } catch (e) { _showToast("Failed to estimate cost", "error"); }
    },

    async run(replace) {
      this.loading = true;
      this.mode = replace ? "repl" : "nd";
      this.expanded = false;
      this.progressTagged = 0;
      this.progressTotal = 0;
      try {
        var resp = await fetch(
          "/api/v1/nodes/" + this.nodeUid + "/smart-tags/generate-all?replace=" + replace,
          { method: "POST", headers: { "X-CSRF-Token": getCsrfToken() } }
        );
        if (!resp.ok) throw new Error("HTTP " + resp.status);

        var reader = resp.body.getReader();
        var decoder = new TextDecoder();
        var buffer = "";
        var totalSkipped = 0;

        while (true) {
          var chunk = await reader.read();
          if (chunk.done) break;
          buffer += decoder.decode(chunk.value, { stream: true });
          var lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (var li = 0; li < lines.length; li++) {
            var line = lines[li].trim();
            if (!line) continue;
            try { var evt = JSON.parse(line); } catch (pe) { continue; }

            if (evt.done) {
              this.progressTagged = evt.tagged_count || this.progressTagged;
              totalSkipped = evt.skipped_count || 0;
              continue;
            }

            // Update progress counter
            if (evt.tagged_so_far) this.progressTagged = evt.tagged_so_far;
            if (evt.total) this.progressTotal = evt.total;

            // Update lightbulbs as each batch arrives
            var results = evt.results || {};
            for (var vid in results) {
              var row = document.querySelector('[data-version-uid="' + vid + '"]');
              if (row) {
                var bulb = row.querySelector(".smart-tag-bulb");
                if (bulb) {
                  bulb.classList.remove("text-[var(--color-text-muted)]");
                  bulb.classList.add("text-yellow-400");
                }
                row.dataset.smartTags = JSON.stringify(results[vid]);
              }
            }
          }
        }

        var verb = replace ? "Replaced" : "Tagged";
        _showToast(verb + " " + this.progressTagged + " facts" +
          (totalSkipped > 0 ? " (" + totalSkipped + " skipped)" : ""));
        document.dispatchEvent(new CustomEvent("ai-usage-changed"));
      } catch (e) {
        console.error("Bulk tagging error:", e);
        if (this.progressTagged > 0) {
          _showToast("Partial: tagged " + this.progressTagged + "/" + this.progressTotal + " before error", "warn");
        } else if (e.message && e.message.indexOf("400") !== -1) {
          _showToast("AI key required. Add one in Settings → AI Key.", "error");
        } else {
          _showToast("Bulk tagging error: " + (e.message || "unknown"), "error");
        }
        document.dispatchEvent(new CustomEvent("ai-usage-changed"));
      } finally {
        this.loading = false;
        this.mode = null;
        this.progressTagged = 0;
        this.progressTotal = 0;
      }
    },

    confirmRun() {
      if (confirm("Replace all auto-generated tags? Manual tags (solid border) will not be affected.")) {
        this.run(true);
      }
    },
  };
}

// === Smart Tags — right pane editor (auto + manual) ===

function smartTagEditor(factUid, versionUid) {
  return {
    factUid: factUid,
    versionUid: versionUid,
    autoTags: [],
    manualTags: [],
    generating: false,
    editingManualIndex: -1,
    editValue: "",
    tagInputValid: true,
    tagInputMessage: "",

    async generateTags() {
      var msg = this.manualTags.length > 0
        ? "Regenerate auto tags? Your " + this.manualTags.length + " manual tag(s) will not be affected."
        : (this.autoTags.length > 0 ? "Regenerate auto tags?" : "Generate smart tags?");
      if (this.autoTags.length > 0 && !confirm(msg)) return;
      this.generating = true;
      try {
        var resp = await fetch(
          "/api/v1/facts/" + this.factUid + "/versions/" + this.versionUid + "/smart-tags/generate",
          { method: "POST", headers: { "X-CSRF-Token": getCsrfToken() } }
        );
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        var data = await resp.json();
        this.autoTags = data.data.tags;
        this._updateRowBulb();
        _showToast("Generated " + this.autoTags.length + " auto tags");
        document.dispatchEvent(new CustomEvent("ai-usage-changed"));
      } catch (e) {
        _showToast("Failed to generate tags", "error");
      } finally {
        this.generating = false;
      }
    },

    async _patchTags(tags, origin) {
      var resp = await fetch(
        "/api/v1/facts/" + this.factUid + "/versions/" + this.versionUid + "/smart-tags",
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfToken() },
          body: JSON.stringify({ tags: tags, origin: origin }),
        }
      );
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      var data = await resp.json();
      if (data.data.rejected && data.data.rejected.length) {
        _showToast("Rejected: " + data.data.rejected.join(", "), "warn");
      }
      return data.data.accepted;
    },

    async removeAutoTag(index) {
      try {
        var newTags = this.autoTags.filter(function (_, i) { return i !== index; });
        this.autoTags = await this._patchTags(newTags, "auto");
        this._updateRowBulb();
      } catch (e) { _showToast("Failed to update tags", "error"); }
    },

    async removeManualTag(index) {
      try {
        var newTags = this.manualTags.filter(function (_, i) { return i !== index; });
        this.manualTags = await this._patchTags(newTags, "manual");
        this._updateRowBulb();
      } catch (e) { _showToast("Failed to update tags", "error"); }
    },

    async addManualTag(inputEl) {
      var text = inputEl.value.trim();
      if (!text) return;
      try {
        var newTags = this.manualTags.concat([text]);
        this.manualTags = await this._patchTags(newTags, "manual");
        this._updateRowBulb();
        this.tagInputValid = true;
        this.tagInputMessage = "";
      } catch (e) { _showToast("Failed to add tag", "error"); }
    },

    startEditManual(index) {
      this.editingManualIndex = index;
      this.editValue = this.manualTags[index];
    },

    async saveEditManual(index) {
      if (this.editingManualIndex !== index) return;
      var text = this.editValue.trim();
      this.editingManualIndex = -1;
      if (!text) return this.removeManualTag(index);
      if (text === this.manualTags[index]) return;
      var newTags = this.manualTags.slice();
      newTags[index] = text;
      try {
        this.manualTags = await this._patchTags(newTags, "manual");
      } catch (e) { _showToast("Failed to update tag", "error"); }
    },

    cancelEdit() {
      this.editingManualIndex = -1;
      this.editValue = "";
    },

    async validateInput(text) {
      if (!text || !text.trim() || text.length < 2) {
        this.tagInputValid = true;
        this.tagInputMessage = "";
        return;
      }
      try {
        var resp = await fetch(
          "/api/v1/facts/" + this.factUid + "/versions/" + this.versionUid + "/smart-tags/validate",
          {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfToken() },
            body: JSON.stringify({ tag: text.trim() }),
          }
        );
        if (!resp.ok) return;
        var data = await resp.json();
        this.tagInputValid = data.data.valid;
        this.tagInputMessage = data.data.valid ? "" : "Tags should contextualize the fact, not repeat it.";
      } catch (e) { /* best-effort */ }
    },

    _updateRowBulb() {
      var row = document.querySelector('[data-fact-uid="' + this.factUid + '"]');
      if (!row) return;
      var bulb = row.querySelector(".smart-tag-bulb");
      if (!bulb) return;
      var total = this.autoTags.length + this.manualTags.length;
      if (total > 0) {
        bulb.classList.remove("text-[var(--color-text-muted)]");
        bulb.classList.add("text-yellow-400");
      } else {
        bulb.classList.remove("text-yellow-400");
        bulb.classList.add("text-[var(--color-text-muted)]");
      }
      row.dataset.smartTags = JSON.stringify(this.autoTags);
      row.dataset.smartTagsManual = JSON.stringify(this.manualTags);
    },
  };
}

// tokenCounter() and formatTokens() are in /static/js/token-counter.js (loaded globally)
