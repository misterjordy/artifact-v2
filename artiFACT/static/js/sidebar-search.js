"use strict";

/**
 * Sidebar collapse-all button for the tree.
 * Search is now handled by the Alpine browseSearch() component in browse.js.
 */
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    var collapseBtn = document.getElementById("sidebar-collapse-btn");
    var treeContainer = document.getElementById("tree-container");

    if (collapseBtn) {
      collapseBtn.addEventListener("click", function () {
        if (!treeContainer) return;
        treeContainer.querySelectorAll("[x-data]").forEach(function (el) {
          if (el.__x) {
            el.__x.$data.open = false;
          } else if (el._x_dataStack) {
            el._x_dataStack[0].open = false;
          }
        });
      });
    }
  });
})();
