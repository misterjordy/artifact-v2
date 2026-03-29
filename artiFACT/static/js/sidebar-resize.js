"use strict";

/**
 * Resizable sidebar via drag handle on right edge.
 * Persists width in localStorage('artifact-sidebar-width').
 */
(function () {
  var STORAGE_KEY = "artifact-sidebar-width";
  var MIN_WIDTH = 180;
  var MAX_WIDTH = 500;

  document.addEventListener("DOMContentLoaded", function () {
    var sidebar = document.querySelector("aside");
    if (!sidebar) return;

    // Restore persisted width
    var saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      var w = parseInt(saved, 10);
      if (w >= MIN_WIDTH && w <= MAX_WIDTH) {
        sidebar.style.width = w + "px";
      }
    }

    // Create drag handle
    var handle = document.createElement("div");
    handle.className = "sidebar-resize-handle";
    handle.setAttribute("role", "separator");
    handle.setAttribute("aria-label", "Resize sidebar");
    sidebar.style.position = "relative";
    sidebar.appendChild(handle);

    var dragging = false;

    handle.addEventListener("mousedown", function (e) {
      e.preventDefault();
      dragging = true;
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    });

    document.addEventListener("mousemove", function (e) {
      if (!dragging) return;
      var newWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, e.clientX));
      sidebar.style.width = newWidth + "px";
    });

    document.addEventListener("mouseup", function () {
      if (!dragging) return;
      dragging = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      localStorage.setItem(STORAGE_KEY, parseInt(sidebar.style.width, 10));
    });
  });
})();
