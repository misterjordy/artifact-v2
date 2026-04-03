"use strict";

function _getCsrf() {
    var m = document.cookie.match(/csrf_token=([^;]+)/);
    return m ? m[1] : "";
}

function _showToast(msg, type) {
    var el = document.createElement("div");
    el.className =
        "fixed bottom-4 right-4 z-50 px-4 py-2 rounded shadow-lg text-sm max-w-sm " +
        (type === "error"
            ? "bg-red-600 text-white"
            : type === "warn"
              ? "bg-yellow-600 text-white"
              : "bg-green-600 text-white");
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function () { el.remove(); }, 4000);
}

var ALPHABET = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

function acronymEditor() {
    return {
        allRows: [],
        filteredRows: [],
        filterQuery: "",
        unresolvedOnly: false,
        selectedUids: [],
        loading: true,
        scanning: false,
        confirmDelete: false,
        dontAskAgain: false,
        pendingDeleteUids: [],
        pendingDeleteCount: 0,
        currentUserUid: null,
        totalCount: 0,
        unresolvedCount: 0,
        alphabetLetters: ALPHABET,
        activeLetter: "",

        async init() {
            var self = this;
            await this.loadAcronyms();

            // ── Sidebar: search input ──
            var filterInput = document.getElementById("acronym-filter-input");
            var clearBtn = document.getElementById("acronym-filter-clear");
            if (filterInput) {
                filterInput.addEventListener("input", function () {
                    self.filterQuery = filterInput.value;
                    self.applyFilter();
                    if (clearBtn) clearBtn.style.display = filterInput.value ? "" : "none";
                });
                filterInput.addEventListener("keydown", function (e) {
                    if (e.key === "Escape") {
                        filterInput.value = "";
                        self.filterQuery = "";
                        self.applyFilter();
                        if (clearBtn) clearBtn.style.display = "none";
                        filterInput.blur();
                    }
                });
            }
            if (clearBtn) {
                clearBtn.style.display = "none";
                clearBtn.addEventListener("click", function () {
                    if (filterInput) filterInput.value = "";
                    self.filterQuery = "";
                    self.applyFilter();
                    clearBtn.style.display = "none";
                });
            }

            // ── Sidebar: buttons ──
            var btnScan = document.getElementById("btn-scan-corpus");
            if (btnScan) btnScan.addEventListener("click", function () { self.scanCorpus(); });

            var btnAdd = document.getElementById("btn-add-acronym");
            if (btnAdd) btnAdd.addEventListener("click", function () { self.addNewRow(); });

            var btnUnresolved = document.getElementById("btn-unresolved-filter");
            if (btnUnresolved) {
                btnUnresolved.addEventListener("click", function () {
                    self.unresolvedOnly = !self.unresolvedOnly;
                    if (self.unresolvedOnly) {
                        btnUnresolved.style.background = "rgba(200,148,58,0.25)";
                        btnUnresolved.style.borderColor = "rgba(200,148,58,0.6)";
                    } else {
                        btnUnresolved.style.background = "";
                        btnUnresolved.style.borderColor = "";
                    }
                    // Force Alpine reactivity update
                    self.filteredRows = self.allRows.filter(function (row) {
                        if (self.unresolvedOnly && row.spelled_out) return false;
                        var q = self.filterQuery.toLowerCase().trim();
                        if (!q) return true;
                        return (
                            row.acronym.toLowerCase().indexOf(q) >= 0 ||
                            (row.spelled_out || "").toLowerCase().indexOf(q) >= 0
                        );
                    });
                    self._updateSidebarStats();
                });
            }

            // ── Sidebar: drop zone ──
            var dropZone = document.getElementById("acronym-drop-zone");
            var fileInput = document.getElementById("acronym-file-input");
            if (dropZone && fileInput) {
                dropZone.addEventListener("click", function (e) {
                    if (e.target === fileInput) return;
                    fileInput.click();
                });
                fileInput.addEventListener("click", function (e) {
                    e.stopPropagation();
                });
                dropZone.addEventListener("dragover", function (e) {
                    e.preventDefault();
                    dropZone.style.borderColor = "var(--color-accent)";
                    dropZone.style.background = "rgba(58,110,165,0.05)";
                });
                dropZone.addEventListener("dragleave", function () {
                    dropZone.style.borderColor = "";
                    dropZone.style.background = "";
                });
                dropZone.addEventListener("drop", function (e) {
                    e.preventDefault();
                    dropZone.style.borderColor = "";
                    dropZone.style.background = "";
                    var file = e.dataTransfer.files[0];
                    if (file) self.processFile(file);
                });
                fileInput.addEventListener("change", function (e) {
                    var file = e.target.files[0];
                    if (file) self.processFile(file);
                    e.target.value = "";
                });
            }

            // Keyboard: Delete key
            document.addEventListener("keydown", function (e) {
                if (e.key === "Delete" && self.selectedUids.length > 0) {
                    e.preventDefault();
                    self.deleteSelected();
                }
            });

            try {
                this.dontAskAgain =
                    sessionStorage.getItem("acronym:dontAskDelete") === "true";
            } catch (_) { /* ignore */ }
        },

        // ── Data loading ──

        async loadAcronyms() {
            this.loading = true;
            try {
                var resp = await fetch("/api/v1/acronyms?limit=10000");
                if (!resp.ok) { _showToast("Failed to load acronyms", "error"); return; }
                var data = await resp.json();
                var rows = data.data || [];
                this.allRows = rows.map(function (row) {
                    return Object.assign({}, row, {
                        _locked: !!row.locked_by_uid,
                        _locked_by: row.locked_by_uid,
                        _looking_up: false,
                        _isNew: false,
                    });
                });
                this._refreshCounts();
                this.applyFilter();
            } finally {
                this.loading = false;
            }
        },

        applyFilter() {
            var q = this.filterQuery.toLowerCase().trim();
            var unresOnly = this.unresolvedOnly;
            this.filteredRows = this.allRows.filter(function (row) {
                if (unresOnly && row.spelled_out) return false;
                if (!q) return true;
                return (
                    row.acronym.toLowerCase().indexOf(q) >= 0 ||
                    (row.spelled_out || "").toLowerCase().indexOf(q) >= 0
                );
            });
            this._updateSidebarStats();
        },

        // ── Selection ──

        toggleSelect(uid) {
            var idx = this.selectedUids.indexOf(uid);
            if (idx >= 0) this.selectedUids.splice(idx, 1);
            else this.selectedUids.push(uid);
        },

        toggleSelectAll(checked) {
            if (checked) this.selectedUids = this.filteredRows.map(function (r) { return r.acronym_uid; });
            else this.selectedUids = [];
        },

        get allSelected() {
            return this.filteredRows.length > 0 &&
                   this.selectedUids.length === this.filteredRows.length;
        },

        // ── Inline editing ──

        async lockRow(row) {
            if (row._isNew) return;
            if (row._locked && row._locked_by !== this.currentUserUid) return;
            try {
                await fetch("/api/v1/acronyms/" + row.acronym_uid + "/lock", {
                    method: "POST",
                    headers: { "X-CSRF-Token": _getCsrf() },
                });
                row._locked = true;
                row._locked_by = this.currentUserUid;
            } catch (_) { /* ignore */ }
        },

        async handleCellBlur(row, field, value) {
            if (row._isNew) {
                await this.saveNewRow(row, field, value);
                return;
            }
            var trimmed = value.trim();
            // Both fields blank = delete the row
            var otherField = field === "acronym" ? "spelled_out" : "acronym";
            var otherVal = row[otherField] || "";
            if (!trimmed && !otherVal) {
                await this._deleteServerRow(row);
                return;
            }
            await this.saveCell(row, field, trimmed);
        },

        async saveCell(row, field, value) {
            if (value === (row[field] || "")) {
                await this.unlockRow(row);
                return;
            }
            try {
                var body = {};
                body[field] = value || null;
                var resp = await fetch("/api/v1/acronyms/" + row.acronym_uid, {
                    method: "PATCH",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRF-Token": _getCsrf(),
                    },
                    body: JSON.stringify(body),
                });
                var data = await resp.json();
                if (!resp.ok) {
                    _showToast((data && data.detail) || "Save failed", "error");
                    return;
                }
                // Update from server response
                if (data.data) {
                    row.acronym = data.data.acronym;
                    row.spelled_out = data.data.spelled_out;
                }
                this._refreshCounts();
            } catch (e) {
                _showToast("Save failed: " + e.message, "error");
            } finally {
                await this.unlockRow(row);
            }
        },

        async unlockRow(row) {
            if (row._isNew) return;
            try {
                await fetch("/api/v1/acronyms/" + row.acronym_uid + "/unlock", {
                    method: "POST",
                    headers: { "X-CSRF-Token": _getCsrf() },
                });
                row._locked = false;
                row._locked_by = null;
            } catch (_) { /* ignore */ }
        },

        // ── Add new ──

        addNewRow() {
            var tempUid = "new-" + Date.now();
            this.allRows.unshift({
                acronym_uid: tempUid,
                acronym: "",
                spelled_out: null,
                _locked: false,
                _locked_by: null,
                _looking_up: false,
                _isNew: true,
            });
            this.applyFilter();
            var self = this;
            this.$nextTick(function () {
                var container = document.getElementById("acronym-scroll-container");
                if (container) container.scrollTop = 0;
                var tbody = self.$el.querySelector("tbody");
                if (tbody) {
                    var input = tbody.querySelector("tr:first-child td:nth-child(2) input");
                    if (input) input.focus();
                }
            });
        },

        async saveNewRow(row, field, value) {
            var trimmed = value.trim();
            if (field === "acronym" && !trimmed) {
                this.allRows = this.allRows.filter(function (r) { return r.acronym_uid !== row.acronym_uid; });
                this.applyFilter();
                return;
            }
            if (field === "acronym") row.acronym = trimmed;
            if (field === "spelled_out") row.spelled_out = trimmed || null;
            if (!row.acronym || field !== "acronym") return;
            try {
                var resp = await fetch("/api/v1/acronyms", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRF-Token": _getCsrf(),
                    },
                    body: JSON.stringify({
                        acronym: row.acronym,
                        spelled_out: row.spelled_out,
                    }),
                });
                var data = await resp.json();
                if (!resp.ok) {
                    _showToast((data && data.detail) || "Create failed", "error");
                    return;
                }
                var idx = this.allRows.findIndex(function (r) { return r.acronym_uid === row.acronym_uid; });
                if (idx >= 0) {
                    this.allRows[idx] = Object.assign({}, data.data, {
                        _locked: false, _locked_by: null,
                        _looking_up: false, _isNew: false,
                    });
                }
                this._refreshCounts();
                this.applyFilter();
            } catch (e) {
                _showToast("Create failed: " + e.message, "error");
            }
        },

        // ── Delete ──

        deleteRow(row) {
            if (row._isNew) {
                this.allRows = this.allRows.filter(function (r) { return r.acronym_uid !== row.acronym_uid; });
                this._refreshCounts();
                this.applyFilter();
                return;
            }
            this.pendingDeleteUids = [row.acronym_uid];
            this.pendingDeleteCount = 1;
            if (this.dontAskAgain) this.confirmAndDelete();
            else this.confirmDelete = true;
        },

        deleteSelected() {
            if (this.selectedUids.length === 0) return;
            this.pendingDeleteUids = this.selectedUids.slice();
            this.pendingDeleteCount = this.selectedUids.length;
            if (this.dontAskAgain) this.confirmAndDelete();
            else this.confirmDelete = true;
        },

        async confirmAndDelete() {
            if (this.dontAskAgain) {
                try { sessionStorage.setItem("acronym:dontAskDelete", "true"); } catch (_) { /* ignore */ }
            }
            this.confirmDelete = false;

            var tempUids = [];
            var serverUids = [];
            var self = this;
            this.pendingDeleteUids.forEach(function (uid) {
                if (typeof uid === "string" && uid.indexOf("new-") === 0) tempUids.push(uid);
                else serverUids.push(uid);
            });

            if (tempUids.length > 0) {
                this.allRows = this.allRows.filter(function (r) { return tempUids.indexOf(r.acronym_uid) < 0; });
            }
            if (serverUids.length > 0) {
                try {
                    var resp = await fetch("/api/v1/acronyms/bulk-delete", {
                        method: "DELETE",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRF-Token": _getCsrf(),
                        },
                        body: JSON.stringify({ acronym_uids: serverUids }),
                    });
                    var data = await resp.json();
                    if (!resp.ok) {
                        _showToast((data && data.detail) || "Delete failed", "error");
                        return;
                    }
                    this.allRows = this.allRows.filter(function (r) { return serverUids.indexOf(r.acronym_uid) < 0; });
                } catch (e) {
                    _showToast("Delete failed: " + e.message, "error");
                    return;
                }
            }

            this.selectedUids = this.selectedUids.filter(function (uid) {
                return self.pendingDeleteUids.indexOf(uid) < 0;
            });
            this.pendingDeleteUids = [];
            this._refreshCounts();
            this.applyFilter();
            document.dispatchEvent(new CustomEvent("acronyms-changed"));
        },

        async _deleteServerRow(row) {
            try {
                var resp = await fetch("/api/v1/acronyms/" + row.acronym_uid, {
                    method: "DELETE",
                    headers: { "X-CSRF-Token": _getCsrf() },
                });
                if (resp.ok) {
                    this.allRows = this.allRows.filter(function (r) { return r.acronym_uid !== row.acronym_uid; });
                    this._refreshCounts();
                    this.applyFilter();
                }
            } catch (_) { /* ignore */ }
        },

        // ── Magic wand ──

        async lookupAcronym(row) {
            row._looking_up = true;
            try {
                var resp = await fetch("/api/v1/acronyms/" + row.acronym_uid + "/lookup", {
                    method: "POST",
                    headers: { "X-CSRF-Token": _getCsrf() },
                });
                var data = await resp.json();
                var expansion = (data.data && data.data.expansion) || data.data;
                if (expansion && expansion !== "UNKNOWN") {
                    await fetch("/api/v1/acronyms/" + row.acronym_uid, {
                        method: "PATCH",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRF-Token": _getCsrf(),
                        },
                        body: JSON.stringify({ spelled_out: expansion }),
                    });
                    row.spelled_out = expansion;
                    this._refreshCounts();
                    document.dispatchEvent(new CustomEvent("ai-usage-changed"));
                    document.dispatchEvent(new CustomEvent("acronyms-changed"));
                } else {
                    _showToast("Could not determine expansion for " + row.acronym, "warn");
                }
            } catch (e) {
                _showToast("Lookup failed: " + e.message, "error");
            } finally {
                row._looking_up = false;
            }
        },

        // ── File upload ──

        async processFile(file) {
            var ext = file.name.split(".").pop().toLowerCase();
            if (ext !== "csv") {
                _showToast("Unsupported file type. Use CSV.", "error");
                return;
            }
            var text = await file.text();
            var items = this._parseCSV(text);
            if (items.length === 0) {
                _showToast("No valid rows found in file", "warn");
                return;
            }
            try {
                var resp = await fetch("/api/v1/acronyms/bulk", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRF-Token": _getCsrf(),
                    },
                    body: JSON.stringify({ items: items }),
                });
                var data = await resp.json();
                if (!resp.ok) {
                    _showToast((data && data.detail) || "Upload failed", "error");
                    return;
                }
                var ins = data.data.inserted;
                var skipped = items.length - ins;
                _showToast("Imported " + ins + " acronyms" +
                    (skipped > 0 ? " (" + skipped + " duplicates skipped)" : ""));
                await this.loadAcronyms();
                document.dispatchEvent(new CustomEvent("acronyms-changed"));
            } catch (e) {
                _showToast("Upload failed: " + e.message, "error");
            }
        },

        _parseCSV(text) {
            var lines = text.split("\n").map(function (l) { return l.trim(); }).filter(Boolean);
            var items = [];
            for (var i = 0; i < lines.length; i++) {
                var parts = lines[i].split(",");
                var col0 = (parts[0] || "").trim().slice(0, 50);
                var col1 = (parts.slice(1).join(",") || "").trim().slice(0, 200);
                if (i === 0 && /acronym|initialism/i.test(col0)) continue;
                if (col0) {
                    items.push({ acronym: col0, spelled_out: col1 || null });
                }
            }
            return items;
        },

        // ── Corpus scan ──

        async scanCorpus() {
            this.scanning = true;
            var btn = document.getElementById("btn-scan-corpus");
            if (btn) btn.textContent = "Scanning...";
            try {
                var resp = await fetch("/api/v1/acronyms/scan-corpus", {
                    method: "POST",
                    headers: { "X-CSRF-Token": _getCsrf() },
                });
                var data = await resp.json();
                _showToast("Found " + data.data.found + ", inserted " + data.data.inserted);
                await this.loadAcronyms();
            } catch (e) {
                _showToast("Scan failed: " + e.message, "error");
            } finally {
                this.scanning = false;
                if (btn) btn.textContent = "Rescan";
            }
        },

        // ── Alphabet scroll ──

        scrollToLetter(letter) {
            this.activeLetter = letter;
            var container = document.getElementById("acronym-scroll-container");
            if (!container) return;
            var selector = letter === "#"
                ? "tr[data-acronym-letter]"
                : 'tr[data-acronym-letter="' + letter + '"]';
            var target = container.querySelector(selector);
            if (target) {
                target.scrollIntoView({ block: "start", behavior: "smooth" });
            }
        },

        // ── Helpers ──

        _refreshCounts() {
            this.totalCount = this.allRows.length;
            this.unresolvedCount = this.allRows.filter(function (r) { return !r.spelled_out; }).length;
            this._updateSidebarStats();
        },

        _updateSidebarStats() {
            var el = document.getElementById("acronym-sidebar-stats");
            if (el) {
                el.textContent = this.totalCount + " entries \u00b7 " +
                    this.unresolvedCount + " unresolved";
            }
        },
    };
}
