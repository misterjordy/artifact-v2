"use strict";

/**
 * Drag-and-drop for taxonomy tree nodes and facts.
 *
 * Nodes drag onto other nodes (node move).
 * Facts drag from center pane onto tree nodes (fact move).
 * Drop opens an inline comment pane; submit calls /api/v1/moves/*.
 */

(function () {
  var DRAG_CLASS = "dnd-drag-over";
  var INVALID_CLASS = "dnd-invalid";

  /* ── Writable UIDs (injected from template) ── */

  function writableUids() {
    return window.__writableNodeUids || [];
  }

  function canWriteTo(uid) {
    var list = writableUids();
    for (var i = 0; i < list.length; i++) {
      if (list[i] === uid) return true;
    }
    return false;
  }

  /* ── CSRF helper ── */

  function csrfToken() {
    var m = document.cookie.match(/csrf_token=([^;]+)/);
    return m ? m[1] : "";
  }

  /* ── Comment pane management ── */

  var openPanes = [];

  function updateCloseAllBtn() {
    var btn = document.getElementById("dnd-close-all-btn");
    if (!btn) return;
    btn.style.display = openPanes.length > 1 ? "" : "none";
  }

  function closeAllPanes() {
    openPanes.slice().forEach(function (el) { el.remove(); });
    openPanes = [];
    updateCloseAllBtn();
  }

  function closePane(el) {
    var idx = openPanes.indexOf(el);
    if (idx !== -1) openPanes.splice(idx, 1);
    el.remove();
    updateCloseAllBtn();
  }

  function createCommentPane(opts) {
    // opts: { moveType, entityUid, targetUid, label, afterEl }
    var pane = document.createElement("div");
    pane.className = "move-comment-pane";
    pane.setAttribute("data-move-type", opts.moveType);
    pane.setAttribute("data-entity-uid", opts.entityUid);
    pane.setAttribute("data-target-uid", opts.targetUid);

    var autoApproveActive = window.__autoApproveActive || false;
    var btnText = autoApproveActive ? "Move" : "Propose Move";

    pane.innerHTML =
      '<div class="move-comment-header">' +
        '<span class="move-comment-label" title="' + escAttr(opts.fullLabel || opts.label) + '">' +
          esc(opts.label) +
        '</span>' +
        '<button class="move-comment-close" aria-label="Close">\u2715</button>' +
      '</div>' +
      '<textarea class="move-comment-textarea" placeholder="Why are you moving this?" rows="2"></textarea>' +
      '<div class="move-comment-error"></div>' +
      '<div class="move-comment-actions">' +
        '<button class="move-comment-submit">' + esc(btnText) + '</button>' +
      '</div>';

    pane.querySelector(".move-comment-close").addEventListener("click", function () {
      closePane(pane);
    });

    pane.querySelector(".move-comment-submit").addEventListener("click", function () {
      submitMove(pane);
    });

    // Allow Enter to submit (Shift+Enter for newline)
    pane.querySelector(".move-comment-textarea").addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submitMove(pane);
      }
    });

    opts.afterEl.insertAdjacentElement("afterend", pane);
    openPanes.push(pane);
    updateCloseAllBtn();
    pane.querySelector(".move-comment-textarea").focus();
    return pane;
  }

  function submitMove(pane) {
    var moveType = pane.getAttribute("data-move-type");
    var entityUid = pane.getAttribute("data-entity-uid");
    var targetUid = pane.getAttribute("data-target-uid");
    var textarea = pane.querySelector(".move-comment-textarea");
    var errorEl = pane.querySelector(".move-comment-error");
    var comment = textarea.value.trim();

    if (!comment) {
      errorEl.textContent = "A comment is required.";
      return;
    }

    errorEl.textContent = "";
    var submitBtn = pane.querySelector(".move-comment-submit");
    submitBtn.disabled = true;
    submitBtn.textContent = "Submitting\u2026";

    var url, body;
    var autoApprove = window.__autoApproveActive || false;

    if (moveType === "node") {
      url = "/api/v1/moves/node";
      body = { node_uid: entityUid, target_parent_uid: targetUid, comment: comment, auto_approve: autoApprove };
    } else {
      url = "/api/v1/moves/fact";
      body = { fact_uid: entityUid, target_node_uid: targetUid, comment: comment, auto_approve: autoApprove };
    }

    fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken(),
      },
      body: JSON.stringify(body),
    })
      .then(function (res) {
        if (!res.ok) return res.json().then(function (d) { throw new Error(d.detail || "Move failed"); });
        return res.json();
      })
      .then(function (data) {
        closePane(pane);
        showToast(data.status === "moved" ? "Moved successfully" : "Move proposed");
        // Refresh tree + center pane
        htmx.trigger("#tree-container", "refreshTree");
        var centerPane = document.getElementById("center-pane");
        if (centerPane) {
          var browseLink = centerPane.querySelector("[hx-get^='/partials/browse/']");
          if (browseLink) {
            var href = browseLink.getAttribute("hx-get");
            htmx.ajax("GET", href, { target: "#center-pane", swap: "innerHTML" });
          }
        }
      })
      .catch(function (err) {
        errorEl.textContent = err.message;
        submitBtn.disabled = false;
        submitBtn.textContent = autoApprove ? "Move" : "Propose Move";
      });
  }

  /* ── Toast ── */

  function showToast(msg) {
    var toast = document.createElement("div");
    toast.className = "dnd-toast";
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(function () { toast.classList.add("dnd-toast-visible"); }, 10);
    setTimeout(function () {
      toast.classList.remove("dnd-toast-visible");
      setTimeout(function () { toast.remove(); }, 300);
    }, 2500);
  }

  /* ── Escape helpers ── */

  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function escAttr(s) {
    return esc(s).replace(/"/g, "&quot;");
  }

  /* ── Drag handlers ── */

  function getNodeRow(el) {
    // Walk up to find the tree node row div
    while (el && !el.hasAttribute("data-node-uid")) {
      el = el.parentElement;
    }
    return el;
  }

  function isDescendantOf(draggedUid, targetUid) {
    // Check if target is a descendant of dragged (for node moves)
    // We use the DOM tree structure
    var draggedEl = document.querySelector('[data-node-uid="' + draggedUid + '"]');
    if (!draggedEl) return false;
    var children = draggedEl.parentElement;
    if (!children) return false;
    return !!children.querySelector('[data-node-uid="' + targetUid + '"]');
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Use event delegation on the tree container and center pane
    var body = document.body;

    /* ── DRAGSTART ── */
    body.addEventListener("dragstart", function (e) {
      var nodeRow = getNodeRow(e.target);

      // Node drag from tree
      if (nodeRow && nodeRow.hasAttribute("data-node-uid")) {
        e.dataTransfer.setData("text/x-move-type", "node");
        e.dataTransfer.setData("text/x-entity-uid", nodeRow.getAttribute("data-node-uid"));
        e.dataTransfer.setData("text/x-entity-label", nodeRow.getAttribute("data-node-title") || "");
        e.dataTransfer.effectAllowed = "move";
        nodeRow.classList.add("dnd-dragging");
        return;
      }

      // Fact drag from center pane
      var factEl = e.target.closest("[data-fact-uid]");
      if (factEl) {
        e.dataTransfer.setData("text/x-move-type", "fact");
        e.dataTransfer.setData("text/x-entity-uid", factEl.getAttribute("data-fact-uid"));
        var sentence = factEl.getAttribute("data-fact-sentence") || "";
        e.dataTransfer.setData("text/x-entity-label", sentence);
        e.dataTransfer.effectAllowed = "move";
        factEl.classList.add("dnd-dragging");
        return;
      }
    });

    /* ── DRAGEND ── */
    body.addEventListener("dragend", function (e) {
      // Remove dragging class from all
      document.querySelectorAll(".dnd-dragging").forEach(function (el) {
        el.classList.remove("dnd-dragging");
      });
      document.querySelectorAll("." + DRAG_CLASS).forEach(function (el) {
        el.classList.remove(DRAG_CLASS);
      });
    });

    /* ── DRAGOVER ── */
    body.addEventListener("dragover", function (e) {
      var nodeRow = getNodeRow(e.target);
      if (!nodeRow || !nodeRow.hasAttribute("data-node-uid")) return;

      var targetUid = nodeRow.getAttribute("data-node-uid");

      // Check writability
      if (!canWriteTo(targetUid)) {
        nodeRow.classList.add(INVALID_CLASS);
        return; // Don't preventDefault — shows not-allowed cursor
      }

      nodeRow.classList.remove(INVALID_CLASS);
      e.preventDefault(); // Allow drop
      e.dataTransfer.dropEffect = "move";
      nodeRow.classList.add(DRAG_CLASS);
    });

    /* ── DRAGLEAVE ── */
    body.addEventListener("dragleave", function (e) {
      var nodeRow = getNodeRow(e.target);
      if (nodeRow) {
        nodeRow.classList.remove(DRAG_CLASS);
        nodeRow.classList.remove(INVALID_CLASS);
      }
    });

    /* ── DROP ── */
    body.addEventListener("drop", function (e) {
      var nodeRow = getNodeRow(e.target);
      if (!nodeRow || !nodeRow.hasAttribute("data-node-uid")) return;

      e.preventDefault();
      nodeRow.classList.remove(DRAG_CLASS);

      var moveType = e.dataTransfer.getData("text/x-move-type");
      var entityUid = e.dataTransfer.getData("text/x-entity-uid");
      var entityLabel = e.dataTransfer.getData("text/x-entity-label");
      var targetUid = nodeRow.getAttribute("data-node-uid");

      if (!moveType || !entityUid || !targetUid) return;

      // Prevent self-drop for nodes
      if (moveType === "node" && entityUid === targetUid) return;

      // Prevent descendant drop for nodes
      if (moveType === "node" && isDescendantOf(entityUid, targetUid)) return;

      // Build label
      var label;
      var fullLabel = entityLabel;
      if (moveType === "fact") {
        label = "Comment on " + truncateSentence(entityLabel, 45) + " move";
      } else {
        label = "Comment on " + (entityLabel || "node") + " move";
      }

      createCommentPane({
        moveType: moveType,
        entityUid: entityUid,
        targetUid: targetUid,
        label: label,
        fullLabel: "Comment on " + fullLabel + " move",
        afterEl: nodeRow.closest(".dnd-node-wrapper") || nodeRow,
      });
    });
  });

  // Expose for the close-all button
  window._dndCloseAllPanes = closeAllPanes;
})();
