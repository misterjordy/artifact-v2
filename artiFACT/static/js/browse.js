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
