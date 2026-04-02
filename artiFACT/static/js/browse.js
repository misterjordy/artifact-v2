"use strict";

function getCsrfToken() {
  var match = document.cookie.match(/csrf_token=([^;]+)/);
  return match ? match[1] : "";
}

document.addEventListener("DOMContentLoaded", function () {
  var logoutLink = document.getElementById("logout-link");
  if (logoutLink) {
    logoutLink.addEventListener("click", async function (e) {
      e.preventDefault();
      await fetch("/api/v1/auth/logout", {
        method: "POST",
        headers: { "X-CSRF-Token": getCsrfToken() },
      });
      window.location.href = "/";
    });
  }

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

// === Smart Tags — lightbulb generate + batch ===

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
      // Light up the bulb
      btn.classList.remove("text-gray-500");
      btn.classList.add("text-yellow-400");
      btn.title = "Smart: " + tags.length + " tags";
      // Update data attribute
      var row = btn.closest("[data-fact-uid]");
      if (row) row.dataset.smartTags = JSON.stringify(tags);
      _showToast("Generated " + tags.length + " smart tags");
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

window.makeAllSmart = function (nodeUid, btn) {
  if (!confirm("Generate smart tags for all untagged facts in this node? This uses your AI key.")) return;
  var origText = btn.querySelector("span").textContent;
  btn.disabled = true;
  btn.querySelector("span").textContent = "Tagging...";

  fetch("/api/v1/nodes/" + nodeUid + "/smart-tags/generate-all", {
    method: "POST",
    headers: { "X-CSRF-Token": getCsrfToken() },
  })
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (data) {
      var results = data.data.results;
      var tagged = data.data.tagged_count;
      var skipped = data.data.skipped_count;
      // Update lightbulbs for tagged facts
      for (var versionUid in results) {
        var row = document.querySelector('[data-version-uid="' + versionUid + '"]');
        if (row) {
          var bulb = row.querySelector(".smart-tag-bulb");
          if (bulb) {
            bulb.classList.remove("text-[var(--color-text-muted)]");
            bulb.classList.add("text-yellow-400");
            bulb.title = "Smart: " + results[versionUid].length + " tags";
          }
          row.dataset.smartTags = JSON.stringify(results[versionUid]);
        }
      }
      _showToast("Tagged " + tagged + " facts (" + skipped + " already had tags)");
    })
    .catch(function (e) {
      if (e.message.indexOf("400") !== -1) {
        _showToast("AI key required. Add one in Settings → AI Key.", "error");
      } else {
        _showToast("Batch tagging failed", "error");
      }
    })
    .finally(function () {
      btn.disabled = false;
      btn.querySelector("span").textContent = origText;
    });
};

// === Smart Tags — right pane Alpine component ===

function smartTagEditor(factUid, versionUid, initialTags) {
  return {
    factUid: factUid,
    versionUid: versionUid,
    tags: initialTags || [],
    generating: false,
    editingIndex: -1,
    editValue: "",
    tagInputValid: true,
    tagInputMessage: "",
    _validateTimer: null,

    async generateTags() {
      if (this.tags.length > 0 && !confirm("Regenerate will replace existing tags. Continue?")) return;
      this.generating = true;
      try {
        var resp = await fetch(
          "/api/v1/facts/" + this.factUid + "/versions/" + this.versionUid + "/smart-tags/generate",
          { method: "POST", headers: { "X-CSRF-Token": getCsrfToken() } }
        );
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        var data = await resp.json();
        this.tags = data.data.tags;
        this._updateRowBulb();
        _showToast("Generated " + this.tags.length + " smart tags");
      } catch (e) {
        if (String(e).indexOf("400") !== -1) {
          _showToast("AI key required. Add one in Settings → AI Key.", "error");
        } else {
          _showToast("Failed to generate tags", "error");
        }
      } finally {
        this.generating = false;
      }
    },

    async saveTags(newTags) {
      try {
        var resp = await fetch(
          "/api/v1/facts/" + this.factUid + "/versions/" + this.versionUid + "/smart-tags",
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfToken() },
            body: JSON.stringify({ tags: newTags }),
          }
        );
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        var data = await resp.json();
        this.tags = data.data.accepted;
        this._updateRowBulb();
        if (data.data.rejected && data.data.rejected.length) {
          _showToast("Rejected: " + data.data.rejected.join(", ") + " (duplicates fact words)", "warn");
        }
      } catch (e) {
        _showToast("Failed to save tags", "error");
      }
    },

    addTag(inputEl) {
      var text = inputEl.value.trim();
      if (!text) return;
      var newTags = this.tags.concat([text]);
      this.saveTags(newTags);
      this.tagInputValid = true;
      this.tagInputMessage = "";
    },

    removeTag(index) {
      var newTags = this.tags.filter(function (_, i) { return i !== index; });
      this.saveTags(newTags);
    },

    startEdit(index) {
      this.editingIndex = index;
      this.editValue = this.tags[index];
      var self = this;
      this.$nextTick(function () {
        var input = self.$refs.editInput;
        if (input) input.focus();
      });
    },

    saveEdit(index) {
      if (this.editingIndex !== index) return;
      var text = this.editValue.trim();
      this.editingIndex = -1;
      if (!text) return this.removeTag(index);
      if (text === this.tags[index]) return;
      var newTags = this.tags.slice();
      newTags[index] = text;
      this.saveTags(newTags);
    },

    cancelEdit() {
      this.editingIndex = -1;
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
      } catch (e) {
        // Validation is best-effort
      }
    },

    _updateRowBulb() {
      var row = document.querySelector('[data-fact-uid="' + this.factUid + '"]');
      if (!row) return;
      var bulb = row.querySelector(".smart-tag-bulb");
      if (!bulb) return;
      if (this.tags.length > 0) {
        bulb.classList.remove("text-[var(--color-text-muted)]");
        bulb.classList.add("text-yellow-400");
        bulb.title = "Smart: " + this.tags.length + " tags";
      } else {
        bulb.classList.remove("text-yellow-400");
        bulb.classList.add("text-[var(--color-text-muted)]");
        bulb.title = "Generate smart tags";
      }
      row.dataset.smartTags = JSON.stringify(this.tags);
    },
  };
}
