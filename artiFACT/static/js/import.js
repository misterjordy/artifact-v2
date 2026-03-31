/* Import pipeline UI logic — tabs, staging review, drag-to-assign, resolution modals. */
"use strict";

function getCsrfToken() {
  var match = document.cookie.match(/csrf_token=([^;]+)/);
  return match ? match[1] : "";
}

function importApp() {
  return {
    // State
    step: "entry",
    activeTab: "paste",
    sessionUid: null,
    programs: [],
    programNodeUid: "",
    effectiveDate: "",
    granularity: "standard",
    pasteText: "",
    selectedFile: null,
    dragOver: false,
    dupWarning: "",
    entryError: "",

    // Progress
    progress: 0,
    progressMessage: "",

    // Staging
    stagedFacts: [],
    sourceName: "",
    viewMode: "grouped",
    selectedFactUid: null,

    // Recommendations
    showingRecs: false,
    currentRecs: [],
    recTargetFact: null,

    // Resolution modal
    resolutionOpen: false,
    resolutionFact: null,
    resolutionType: "",
    resolutionExistingSentence: "",

    // Group relocate
    relocateOpen: false,
    relocateGroup: null,

    // Node constraints
    constraintNodeUids: [],

    // Done
    doneMessage: "",

    init() {
      // Read server data from data-* attributes (safe from HTML escaping issues)
      var el = this.$el;
      try {
        this.programs = JSON.parse(el.dataset.programs || "[]");
      } catch (e) {
        this.programs = [];
      }
      this.effectiveDate = el.dataset.today || new Date().toISOString().slice(0, 10);
      if (this.programs.length === 1) {
        this.programNodeUid = this.programs[0].node_uid;
      }
    },

    // === Computed ===

    get canStart() {
      if (!this.programNodeUid || !this.effectiveDate) return false;
      if (this.activeTab === "paste" && this.pasteText.length < 10) return false;
      if (this.activeTab === "upload" && !this.selectedFile) return false;
      return true;
    },

    get badgeCounts() {
      var counts = { pending: 0, duplicate: 0, conflict: 0, orphaned: 0, accepted: 0, deleted: 0 };
      this.stagedFacts.forEach(function (f) {
        if (f.status === "pending" || f.status === "accepted") counts.pending++;
        else if (counts[f.status] !== undefined) counts[f.status]++;
      });
      return counts;
    },

    get readyCount() {
      return this.stagedFacts.filter(function (f) {
        return f.status === "pending" || f.status === "accepted";
      }).length;
    },

    get unresolvedCount() {
      return this.stagedFacts.filter(function (f) {
        return f.status === "duplicate" || f.status === "conflict";
      }).length;
    },

    get groupedFacts() {
      var groups = {};
      var orphaned = [];
      var self = this;
      this.stagedFacts.forEach(function (f) {
        if (f.status === "deleted") return;
        if (!f.suggested_node_uid || f.status === "orphaned") {
          orphaned.push(f);
          return;
        }
        var key = f.suggested_node_uid;
        if (!groups[key]) {
          groups[key] = { nodeUid: key, title: f.node_title || "Unknown Node", facts: [] };
        }
        groups[key].facts.push(f);
      });
      var result = Object.values(groups);
      if (orphaned.length > 0) {
        result.push({ nodeUid: null, title: "Orphaned Facts", facts: orphaned });
      }
      return result;
    },

    // === File handling ===

    handleFileDrop(event) {
      this.dragOver = false;
      var files = event.dataTransfer.files;
      if (files.length > 0) this.selectedFile = files[0];
    },

    handleFileSelect(event) {
      var files = event.target.files;
      if (files.length > 0) this.selectedFile = files[0];
    },

    // === Start analysis ===

    async startAnalysis() {
      this.entryError = "";
      var csrf = getCsrfToken();

      if (this.activeTab === "paste") {
        await this._startPaste(csrf);
      } else {
        await this._startUpload(csrf);
      }
    },

    async _startPaste(csrf) {
      try {
        var body = {
          text: this.pasteText,
          program_node_uid: this.programNodeUid,
          effective_date: this.effectiveDate,
          granularity: this.granularity,
        };
        if (this.constraintNodeUids.length > 0) {
          body.constraint_node_uids = this.constraintNodeUids;
        }
        var resp = await fetch("/api/v1/import/paste", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify(body),
        });
        if (!resp.ok) {
          var err = await resp.json();
          this.entryError = err.detail || "Paste import failed";
          return;
        }
        var data = await resp.json();
        this.sessionUid = data.session_uid;
        this.sourceName = "Pasted text";
        this.step = "analyzing";
        this.listenProgress();
      } catch (e) {
        this.entryError = e.message || "Network error";
      }
    },

    async _startUpload(csrf) {
      try {
        var formData = new FormData();
        formData.append("file", this.selectedFile);
        formData.append("program_node_uid", this.programNodeUid);
        formData.append("effective_date", this.effectiveDate);
        formData.append("granularity", this.granularity);

        var resp = await fetch("/api/v1/import/upload", {
          method: "POST",
          headers: { "X-CSRF-Token": csrf },
          body: formData,
        });
        if (!resp.ok) {
          var err = await resp.json();
          if (resp.status === 409) {
            this.dupWarning = err.detail || "This document was already imported.";
            return;
          }
          this.entryError = err.detail || "Upload failed";
          return;
        }
        var data = await resp.json();
        this.sessionUid = data.session_uid;
        this.sourceName = this.selectedFile.name;

        // Trigger analysis
        var analyzeResp = await fetch("/api/v1/import/analyze/" + this.sessionUid, {
          method: "POST",
          headers: { "X-CSRF-Token": csrf },
        });
        if (!analyzeResp.ok) {
          var err2 = await analyzeResp.json();
          this.entryError = err2.detail || "Analysis trigger failed";
          return;
        }

        this.step = "analyzing";
        this.listenProgress();
      } catch (e) {
        this.entryError = e.message || "Network error";
      }
    },

    // === SSE Progress ===

    listenProgress() {
      var self = this;
      var source = new EventSource("/api/v1/import/sessions/" + this.sessionUid + "/progress");
      source.onmessage = function (event) {
        var data = JSON.parse(event.data);
        self.progress = Math.max(0, Math.min(100, data.percent));
        self.progressMessage = data.message;
        if (data.percent >= 100) {
          source.close();
          self.loadStaged();
        } else if (data.percent < 0) {
          source.close();
          self.entryError = data.message;
          self.step = "entry";
        }
      };
      source.onerror = function () {
        source.close();
        self.loadStaged();
      };
    },

    // === Load staged facts ===

    async loadStaged() {
      try {
        var resp = await fetch("/api/v1/import/sessions/" + this.sessionUid + "/staged");
        if (!resp.ok) {
          this.entryError = "Failed to load staged facts";
          this.step = "entry";
          return;
        }
        var data = await resp.json();
        this.stagedFacts = data.facts;
        this.step = "review";
      } catch (e) {
        this.entryError = e.message;
        this.step = "entry";
      }
    },

    // === Fact interactions ===

    selectFact(fact) {
      if (fact.status === "deleted") return;
      this.selectedFactUid = this.selectedFactUid === fact.staged_fact_uid ? null : fact.staged_fact_uid;
    },

    async onSentenceEdit(event, fact) {
      var newText = event.target.textContent.trim();
      if (newText === fact.display_sentence || !newText) {
        event.target.textContent = fact.display_sentence;
        return;
      }
      await this.patchFact(fact.staged_fact_uid, { display_sentence: newText });
      fact.display_sentence = newText;
    },

    async deleteFact(fact) {
      await this.patchFact(fact.staged_fact_uid, { status: "deleted" });
      fact.status = "deleted";
    },

    // === Drag to tree ===

    onFactDragStart(event, fact) {
      event.dataTransfer.setData("text/plain", fact.staged_fact_uid);
      event.dataTransfer.effectAllowed = "move";
    },

    // === Resolution modal ===

    openResolution(fact, type) {
      this.resolutionFact = fact;
      this.resolutionType = type;
      this.resolutionExistingSentence = fact.existing_sentence || "(Existing fact not available)";
      this.resolutionOpen = true;
    },

    async resolveAs(resolution) {
      var fact = this.resolutionFact;
      if (!fact) return;

      var patch = { resolution: resolution };
      if (resolution === "keep_new") {
        patch.status = "accepted";
      } else if (resolution === "keep_existing") {
        patch.status = "rejected";
      } else if (resolution === "keep_both") {
        patch.status = "accepted";
      }

      await this.patchFact(fact.staged_fact_uid, patch);
      Object.assign(fact, patch);
      this.resolutionOpen = false;
    },

    editResolutionFact() {
      // Close modal, focus the fact's text for inline editing
      this.resolutionOpen = false;
      var uid = this.resolutionFact ? this.resolutionFact.staged_fact_uid : null;
      if (!uid) return;
      this.$nextTick(function () {
        var el = document.querySelector('[data-staged-uid="' + uid + '"] [contenteditable]');
        if (el) {
          el.focus();
          // Select all text
          var range = document.createRange();
          range.selectNodeContents(el);
          var sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
        }
      });
    },

    // === AI Recommendations ===

    showRecommendations(fact) {
      this.recTargetFact = fact;
      var alts = fact.node_alternatives || [];
      // Resolve node titles from the tree
      this.currentRecs = alts.map(function (alt) {
        return {
          node_uid: alt.node_uid,
          confidence: alt.confidence || 0,
          reason: alt.reason || "",
          node_title: alt.node_title || alt.node_uid,
        };
      });
      this.showingRecs = true;
    },

    showGroupRecommendation(group) {
      if (group.facts.length > 0) {
        this.showRecommendations(group.facts[0]);
      }
    },

    async applyRecommendation(rec) {
      var fact = this.recTargetFact;
      if (!fact) return;
      await this.patchFact(fact.staged_fact_uid, { suggested_node_uid: rec.node_uid });
      fact.suggested_node_uid = rec.node_uid;
      fact.node_title = rec.node_title;
      this.showingRecs = false;
    },

    // === Group operations ===

    groupRelocate(group) {
      this.relocateGroup = group;
      this.relocateOpen = true;
      // Enable tree click to assign mode
    },

    async deleteGroup(group) {
      if (!confirm("Delete all " + group.facts.length + " facts in '" + group.title + "'?")) return;
      for (var i = 0; i < group.facts.length; i++) {
        await this.patchFact(group.facts[i].staged_fact_uid, { status: "deleted" });
        group.facts[i].status = "deleted";
      }
    },

    // === Node constraint toggle (called from tree click) ===

    toggleConstraint(nodeUid) {
      var idx = this.constraintNodeUids.indexOf(nodeUid);
      if (idx > -1) {
        this.constraintNodeUids.splice(idx, 1);
      } else {
        this.constraintNodeUids.push(nodeUid);
      }
      this.$dispatch("constraint-changed");
    },

    updateConstraintDisplay() {
      var el = document.getElementById("import-constraint-display");
      if (!el) return;
      if (this.constraintNodeUids.length === 0) {
        el.textContent = "No constraints \u2014 AI will suggest from entire taxonomy";
      } else {
        el.textContent = "Constraining to: " + this.constraintNodeUids.length + " node(s)";
      }
    },

    // === Reset / Rerun / Propose ===

    async confirmReset() {
      if (!confirm("This will delete all staged facts and reset the import session. Continue?")) return;
      var csrf = getCsrfToken();
      await fetch("/api/v1/import/sessions/" + this.sessionUid + "/reset", {
        method: "POST",
        headers: { "X-CSRF-Token": csrf },
      });
      this.resetToEntry();
    },

    async rerunAnalysis() {
      var csrf = getCsrfToken();
      this.step = "analyzing";
      this.progress = 0;
      this.progressMessage = "Re-analyzing...";
      await fetch("/api/v1/import/sessions/" + this.sessionUid + "/rerun", {
        method: "POST",
        headers: { "X-CSRF-Token": csrf },
      });
      this.listenProgress();
    },

    async proposeImport() {
      var csrf = getCsrfToken();
      // Collect indices of accepted/pending facts
      var accepted = [];
      this.stagedFacts.forEach(function (f, i) {
        if (f.status === "pending" || f.status === "accepted") {
          accepted.push(i);
        }
      });
      if (accepted.length === 0) return;

      try {
        var resp = await fetch("/api/v1/import/sessions/" + this.sessionUid + "/propose", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify({ accepted_indices: accepted }),
        });
        if (!resp.ok) {
          var err = await resp.json();
          alert(err.detail || "Propose failed");
          return;
        }
        var data = await resp.json();
        this.doneMessage = data.created_count + " facts imported successfully.";
        this.step = "done";
      } catch (e) {
        alert(e.message || "Network error");
      }
    },

    async downloadUnresolved() {
      window.open("/api/v1/import/sessions/" + this.sessionUid + "/download-unresolved", "_blank");
    },

    resetToEntry() {
      this.step = "entry";
      this.sessionUid = null;
      this.progress = 0;
      this.progressMessage = "";
      this.stagedFacts = [];
      this.entryError = "";
      this.doneMessage = "";
      this.pasteText = "";
      this.selectedFile = null;
      this.dupWarning = "";
      this.selectedFactUid = null;
    },

    // === API helper ===

    async patchFact(uid, data) {
      var csrf = getCsrfToken();
      await fetch("/api/v1/import/staged/" + uid, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify(data),
      });
    },

    // === Tree node assignment (called externally) ===

    async assignToNode(nodeUid, nodeTitle) {
      // If relocating a group, move all facts
      if (this.relocateOpen && this.relocateGroup) {
        var group = this.relocateGroup;
        for (var i = 0; i < group.facts.length; i++) {
          await this.patchFact(group.facts[i].staged_fact_uid, { suggested_node_uid: nodeUid });
          group.facts[i].suggested_node_uid = nodeUid;
          group.facts[i].node_title = nodeTitle;
        }
        this.relocateOpen = false;
        this.relocateGroup = null;
        return;
      }
      // If a single fact is selected, assign it
      if (this.selectedFactUid) {
        var fact = this.stagedFacts.find(function (f) {
          return f.staged_fact_uid === this.selectedFactUid;
        }.bind(this));
        if (fact) {
          await this.patchFact(fact.staged_fact_uid, { suggested_node_uid: nodeUid });
          fact.suggested_node_uid = nodeUid;
          fact.node_title = nodeTitle;
          if (fact.status === "orphaned") fact.status = "pending";
          this.selectedFactUid = null;
        }
      }
    },
  };
}

// === Tree integration ===
// After DOM load, attach import-specific behaviors to the tree

document.addEventListener("DOMContentLoaded", function () {
  // Intercept tree node clicks for import page (constraint toggle + assign)
  document.addEventListener("click", function (e) {
    var nodeEl = e.target.closest("[data-node-uid]");
    if (!nodeEl) return;

    var importRoot = document.getElementById("import-root");
    if (!importRoot) return;

    var appData = Alpine.$data(importRoot);
    if (!appData) return;

    var nodeUid = nodeEl.dataset.nodeUid;
    var nodeTitle = nodeEl.dataset.nodeTitle || "Unknown";

    // If in entry step, toggle constraint
    if (appData.step === "entry") {
      e.preventDefault();
      e.stopPropagation();
      appData.toggleConstraint(nodeUid);
      // Visual toggle
      nodeEl.classList.toggle("import-constraint-active");
      return;
    }

    // If in review step and a fact is selected or relocating, assign
    if (appData.step === "review" && (appData.selectedFactUid || appData.relocateOpen)) {
      e.preventDefault();
      e.stopPropagation();
      appData.assignToNode(nodeUid, nodeTitle);
    }
  });

  // Handle drop of facts onto tree nodes
  document.addEventListener("dragover", function (e) {
    var nodeEl = e.target.closest("[data-node-uid]");
    if (nodeEl) {
      e.preventDefault();
      nodeEl.classList.add("dnd-drag-over");
    }
  });

  document.addEventListener("dragleave", function (e) {
    var nodeEl = e.target.closest("[data-node-uid]");
    if (nodeEl) {
      nodeEl.classList.remove("dnd-drag-over");
    }
  });

  document.addEventListener("drop", function (e) {
    var nodeEl = e.target.closest("[data-node-uid]");
    if (!nodeEl) return;

    nodeEl.classList.remove("dnd-drag-over");
    var stagedUid = e.dataTransfer.getData("text/plain");
    if (!stagedUid) return;

    e.preventDefault();
    var importRoot = document.getElementById("import-root");
    if (!importRoot) return;

    var appData = Alpine.$data(importRoot);
    if (!appData) return;

    var nodeUid = nodeEl.dataset.nodeUid;
    var nodeTitle = nodeEl.dataset.nodeTitle || "Unknown";

    var fact = appData.stagedFacts.find(function (f) { return f.staged_fact_uid === stagedUid; });
    if (fact) {
      appData.patchFact(fact.staged_fact_uid, { suggested_node_uid: nodeUid });
      fact.suggested_node_uid = nodeUid;
      fact.node_title = nodeTitle;
      if (fact.status === "orphaned") fact.status = "pending";
    }
  });
});
