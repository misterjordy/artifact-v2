"use strict";

/**
 * Undo pane: Ctrl+Z keybinding, Alpine.js component for undo interactions.
 */

/* ── Ctrl+Z / Cmd+Z global keybinding ── */
document.addEventListener("keydown", function (e) {
  if ((e.ctrlKey || e.metaKey) && e.key === "z") {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.isContentEditable) {
      return;
    }
    e.preventDefault();
    openUndoPane();
  }
});

function openUndoPane() {
  window.openRightPane("Recent Actions");
  htmx.ajax("GET", "/partials/undo-actions", {
    target: "#right-pane-content",
    swap: "innerHTML",
  });
}

/* ── Toast utility (reuses dnd-toast CSS) ── */
function showUndoToast(msg) {
  var toast = document.createElement("div");
  toast.className = "dnd-toast";
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(function () { toast.classList.add("dnd-toast-visible"); }, 10);
  setTimeout(function () {
    toast.classList.remove("dnd-toast-visible");
    setTimeout(function () { toast.remove(); }, 300);
  }, 2000);
}

/* ── Alpine.js component ── */
function undoPane() {
  return {
    async undoSingle(eventUid, refKey) {
      var line = this.$refs[refKey];
      var btn = event.target;
      btn.disabled = true;
      btn.textContent = "...";

      var resp = await fetch("/api/v1/undo/" + eventUid, {
        method: "POST",
        headers: {
          "X-CSRF-Token": getCsrfToken(),
          "Content-Type": "application/json",
        },
      });

      if (resp.ok) {
        if (line) {
          line.style.transition = "opacity 0.3s, max-height 0.3s, margin 0.3s, padding 0.3s";
          line.style.opacity = "0";
          line.style.maxHeight = "0";
          line.style.overflow = "hidden";
          line.style.marginTop = "0";
          line.style.marginBottom = "0";
          line.style.paddingTop = "0";
          line.style.paddingBottom = "0";
          setTimeout(function () { line.remove(); }, 350);
        }
        showUndoToast("Action undone");
      } else {
        var data = {};
        try { data = await resp.json(); } catch (_) { /* ignore */ }
        btn.textContent = "Undo";
        btn.disabled = false;
        if (line) {
          var err = line.querySelector(".undo-inline-error");
          if (!err) {
            err = document.createElement("div");
            err.className = "undo-inline-error text-2xs text-[var(--color-danger)] mt-1";
            line.appendChild(err);
          }
          err.textContent = data.detail || "Could not undo";
        }
      }
    },

    async undoBulk(eventUidsJson, refKey) {
      var eventUids = JSON.parse(eventUidsJson);
      var line = this.$refs[refKey];
      var btn = event.target;
      btn.disabled = true;
      btn.textContent = "...";

      var resp = await fetch("/api/v1/undo/bulk", {
        method: "POST",
        headers: {
          "X-CSRF-Token": getCsrfToken(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ event_uids: eventUids }),
      });

      if (resp.ok) {
        if (line) {
          line.style.transition = "opacity 0.3s, max-height 0.3s, margin 0.3s, padding 0.3s";
          line.style.opacity = "0";
          line.style.maxHeight = "0";
          line.style.overflow = "hidden";
          line.style.marginTop = "0";
          line.style.marginBottom = "0";
          line.style.paddingTop = "0";
          line.style.paddingBottom = "0";
          setTimeout(function () { line.remove(); }, 350);
        }
        showUndoToast("Undid " + eventUids.length + " actions");
      } else {
        var data = {};
        try { data = await resp.json(); } catch (_) { /* ignore */ }
        btn.textContent = "Undo " + eventUids.length;
        btn.disabled = false;
        if (line) {
          var err = line.querySelector(".undo-inline-error");
          if (!err) {
            err = document.createElement("div");
            err.className = "undo-inline-error text-2xs text-[var(--color-danger)] mt-1";
            line.appendChild(err);
          }
          err.textContent = data.detail || "Could not undo";
        }
      }
    },
  };
}
