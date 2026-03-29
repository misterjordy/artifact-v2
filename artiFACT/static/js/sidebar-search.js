"use strict";

/**
 * Sidebar taxonomy search with debounce, Escape to clear, and collapse-all button.
 */
(function () {
  var DEBOUNCE_MS = 250;
  var MIN_CHARS = 2;

  document.addEventListener("DOMContentLoaded", function () {
    var input = document.getElementById("sidebar-search-input");
    var collapseBtn = document.getElementById("sidebar-collapse-btn");
    var clearBtn = document.getElementById("sidebar-clear-btn");
    var treeContainer = document.getElementById("tree-container");
    var searchResultsContainer = document.getElementById("sidebar-search-results");
    if (!input) return;

    var debounceTimer = null;
    var isSearching = false;

    function showCollapseBtn() {
      if (collapseBtn) collapseBtn.classList.remove("hidden");
      if (clearBtn) clearBtn.classList.add("hidden");
    }

    function showClearBtn() {
      if (collapseBtn) collapseBtn.classList.add("hidden");
      if (clearBtn) clearBtn.classList.remove("hidden");
    }

    function clearSearch() {
      input.value = "";
      showCollapseBtn();
      if (searchResultsContainer) searchResultsContainer.innerHTML = "";
      if (searchResultsContainer) searchResultsContainer.classList.add("hidden");
      if (treeContainer) treeContainer.classList.remove("hidden");
      isSearching = false;
    }

    function collapseAll() {
      if (!treeContainer) return;
      treeContainer.querySelectorAll("[x-data]").forEach(function (el) {
        if (el.__x) {
          el.__x.$data.open = false;
        } else if (el._x_dataStack) {
          el._x_dataStack[0].open = false;
        }
      });
    }

    function doSearch(query) {
      if (query.length < MIN_CHARS) {
        clearSearch();
        return;
      }
      isSearching = true;
      showClearBtn();
      if (treeContainer) treeContainer.classList.add("hidden");
      if (searchResultsContainer) searchResultsContainer.classList.remove("hidden");

      // Get active program filters
      var programFilter = "";
      document.querySelectorAll(".search-program-filter.active").forEach(function (el) {
        programFilter += "&program_uid=" + el.dataset.uid;
      });

      htmx.ajax("GET", "/partials/search-results?q=" + encodeURIComponent(query) + programFilter, {
        target: "#sidebar-search-results",
        swap: "innerHTML",
      });
    }

    input.addEventListener("input", function () {
      clearTimeout(debounceTimer);
      var q = input.value.trim();
      if (q.length > 0) {
        showClearBtn();
      } else {
        clearSearch();
        return;
      }
      debounceTimer = setTimeout(function () {
        doSearch(q);
      }, DEBOUNCE_MS);
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        e.preventDefault();
        clearSearch();
        input.blur();
      }
    });

    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        clearSearch();
        input.focus();
      });
    }

    if (collapseBtn) {
      collapseBtn.addEventListener("click", function () {
        collapseAll();
      });
    }

    // When a search result is clicked, clear search and restore tree
    document.addEventListener("click", function (e) {
      var link = e.target.closest("[data-search-result]");
      if (link) {
        clearSearch();
      }
    });
  });
})();
