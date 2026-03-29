"use strict";

/**
 * Right slideout pane: animated slide in/out + resizable left edge.
 * Persists width in localStorage('artifact-right-pane-width').
 */
(function () {
  var STORAGE_KEY = "artifact-right-pane-width";
  var MIN_WIDTH = 280;
  var MAX_WIDTH = 700;
  var DEFAULT_WIDTH = 380;

  window.openRightPane = function (title) {
    var pane = document.getElementById("right-pane");
    var titleEl = document.getElementById("right-pane-title");
    if (!pane) return;
    if (titleEl && title) titleEl.textContent = title;
    pane.classList.add("open");
  };

  window.closeRightPane = function () {
    var pane = document.getElementById("right-pane");
    if (!pane) return;
    pane.classList.remove("open");
    // Clear content after the slide-out animation completes
    setTimeout(function () {
      if (!pane.classList.contains("open")) {
        var content = document.getElementById("right-pane-content");
        if (content) content.innerHTML = "";
      }
    }, 250);
  };

  document.addEventListener("DOMContentLoaded", function () {
    var pane = document.getElementById("right-pane");
    var closeBtn = document.getElementById("right-pane-close");
    if (!pane) return;

    // Restore persisted width
    var saved = localStorage.getItem(STORAGE_KEY);
    var w = saved ? parseInt(saved, 10) : DEFAULT_WIDTH;
    if (w >= MIN_WIDTH && w <= MAX_WIDTH) {
      pane.style.width = w + "px";
    } else {
      pane.style.width = DEFAULT_WIDTH + "px";
    }

    // Close button
    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        window.closeRightPane();
      });
    }

    // Escape to close
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && pane.classList.contains("open")) {
        window.closeRightPane();
      }
    });

    // Create resize handle on LEFT edge
    var handle = document.createElement("div");
    handle.className = "right-pane-resize-handle";
    handle.setAttribute("role", "separator");
    handle.setAttribute("aria-label", "Resize panel");
    pane.appendChild(handle);

    var dragging = false;

    handle.addEventListener("mousedown", function (e) {
      e.preventDefault();
      dragging = true;
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    });

    document.addEventListener("mousemove", function (e) {
      if (!dragging) return;
      var newWidth = window.innerWidth - e.clientX;
      newWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, newWidth));
      pane.style.width = newWidth + "px";
    });

    document.addEventListener("mouseup", function () {
      if (!dragging) return;
      dragging = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      localStorage.setItem(STORAGE_KEY, parseInt(pane.style.width, 10));
    });

    // Listen for HTMX events that want to open the right pane
    document.body.addEventListener("openRightPane", function (evt) {
      var title = (evt.detail && evt.detail.title) || "";
      window.openRightPane(title);
    });
  });
})();
