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
    programNodeTitle: "",
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
    progressLog: [],

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

    // Node constraints (drag-drop)
    constraintNodeUids: [],
    constraintNodes: [],   // [{uid, title}]

    // Done
    doneMessage: "",
    proposing: false,

    // History
    history: [],

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

      // Resume active session if one exists
      var activeRaw = el.dataset.activeSession || "{}";
      try {
        var active = JSON.parse(activeRaw);
        if (active && active.session_uid) {
          this.sessionUid = active.session_uid;
          this.sourceName = active.input_type === "text" ? "Pasted text" : active.source_filename;
          if (active.status === "analyzing") {
            this.step = "analyzing";
            this.listenProgress();
          } else if (active.status === "staged") {
            this.loadStaged();
          }
        }
      } catch (e) {
        // No active session, show entry form
      }

      this.loadHistory();
    },

    async loadHistory() {
      try {
        var resp = await fetch("/api/v1/import/sessions?mine=true");
        if (resp.ok) {
          var data = await resp.json();
          this.history = data.data || [];
        }
      } catch (e) {
        // silently fail
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
      this.progressLog = ["Connecting to analysis pipeline\u2026"];
      var source = new EventSource("/api/v1/import/sessions/" + this.sessionUid + "/progress");
      source.onmessage = function (event) {
        var data = JSON.parse(event.data);
        self.progress = Math.max(0, Math.min(100, data.percent));
        self.progressMessage = data.message;
        // Add new message to log if it's different from the last one
        if (data.message && (self.progressLog.length === 0 || self.progressLog[self.progressLog.length - 1] !== data.message)) {
          self.progressLog.push(data.message);
        }
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
        // Don't immediately load staged — poll the session status first
        self._pollSessionStatus();
      };
    },

    async _pollSessionStatus() {
      // When SSE disconnects, check actual session status before deciding what to do
      try {
        var resp = await fetch("/api/v1/import/sessions/" + this.sessionUid);
        if (!resp.ok) {
          this.entryError = "Lost connection to analysis pipeline";
          this.step = "entry";
          return;
        }
        var data = await resp.json();
        if (data.status === "staged") {
          this.loadStaged();
        } else if (data.status === "failed") {
          this.entryError = data.error_message || "Analysis failed";
          this.step = "entry";
        } else if (data.status === "analyzing") {
          // Still analyzing — reconnect SSE after a brief pause
          var self = this;
          setTimeout(function () { self.listenProgress(); }, 2000);
        } else {
          this.entryError = "Unexpected session status: " + data.status;
          this.step = "entry";
        }
      } catch (e) {
        this.entryError = "Lost connection. Refresh the page to check status.";
        this.step = "entry";
      }
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

    // === Drag-drop handlers for program + constraint zones ===

    handleProgramDrop(event) {
      event.currentTarget.classList.remove("dnd-drag-over");
      var uid = event.dataTransfer.getData("text/plain");
      var title = event.dataTransfer.getData("text/x-node-title") || this._getNodeTitleFromDom(uid);
      if (uid) {
        this.programNodeUid = uid;
        this.programNodeTitle = title || uid;
      }
    },

    handleConstraintDrop(event) {
      event.currentTarget.classList.remove("dnd-drag-over");
      var uid = event.dataTransfer.getData("text/plain");
      var title = event.dataTransfer.getData("text/x-node-title") || this._getNodeTitleFromDom(uid);
      if (uid && this.constraintNodeUids.indexOf(uid) === -1) {
        this.constraintNodeUids.push(uid);
        this.constraintNodes.push({ uid: uid, title: title || uid });
      }
    },

    removeConstraint(index) {
      this.constraintNodeUids.splice(index, 1);
      this.constraintNodes.splice(index, 1);
    },

    _getNodeTitleFromDom(uid) {
      var el = document.querySelector('[data-node-uid="' + uid + '"]');
      return el ? (el.dataset.nodeTitle || "") : "";
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
      if (this.proposing) return;
      this.proposing = true;
      var csrf = getCsrfToken();

      try {
        var resp = await fetch("/api/v1/import/sessions/" + this.sessionUid + "/propose", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        });
        if (!resp.ok) {
          var err = await resp.json();
          alert(err.detail || "Propose failed");
          this.proposing = false;
          return;
        }
        var data = await resp.json();
        var r = data.data || {};
        var total = (r.created || 0) + (r.edited || 0);
        this.doneMessage = total + " facts proposed (" + (r.created || 0) + " new, " + (r.edited || 0) + " corrections, " + (r.skipped || 0) + " skipped).";
        this.step = "done";
        this.loadHistory();
      } catch (e) {
        alert(e.message || "Network error");
      }
      this.proposing = false;
    },

    async downloadUnresolved() {
      window.open("/api/v1/import/sessions/" + this.sessionUid + "/download-unresolved", "_blank");
    },

    resetToEntry() {
      this.step = "entry";
      this.sessionUid = null;
      this.progress = 0;
      this.progressMessage = "";
      this.progressLog = [];
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
  // Set node title in dragstart so drop zones can read it
  document.addEventListener("dragstart", function (e) {
    var nodeEl = e.target.closest("[data-node-uid]");
    if (nodeEl) {
      e.dataTransfer.setData("text/plain", nodeEl.dataset.nodeUid);
      e.dataTransfer.setData("text/x-node-title", nodeEl.dataset.nodeTitle || "");
      e.dataTransfer.effectAllowed = "copyMove";
    }
  });

  // Tree node clicks: in review step, assign selected fact / relocate group
  document.addEventListener("click", function (e) {
    var nodeEl = e.target.closest("[data-node-uid]");
    if (!nodeEl) return;

    var importRoot = document.getElementById("import-root");
    if (!importRoot) return;

    var appData = Alpine.$data(importRoot);
    if (!appData) return;

    var nodeUid = nodeEl.dataset.nodeUid;
    var nodeTitle = nodeEl.dataset.nodeTitle || "Unknown";

    // In review step and a fact is selected or relocating, assign
    if (appData.step === "review" && (appData.selectedFactUid || appData.relocateOpen)) {
      e.preventDefault();
      e.stopPropagation();
      appData.assignToNode(nodeUid, nodeTitle);
    }
  });

  // Handle drop of staged facts onto tree nodes (review step)
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

    // Only handle staged fact drops onto tree (UUID format check)
    if (stagedUid.length < 30) return;

    var importRoot = document.getElementById("import-root");
    if (!importRoot) return;

    var appData = Alpine.$data(importRoot);
    if (!appData || appData.step !== "review") return;

    e.preventDefault();
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
