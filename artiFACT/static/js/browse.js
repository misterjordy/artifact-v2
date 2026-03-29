"use strict";

document.addEventListener("DOMContentLoaded", function () {
  var logoutLink = document.getElementById("logout-link");
  if (logoutLink) {
    logoutLink.addEventListener("click", async function (e) {
      e.preventDefault();
      var match = document.cookie.match(/csrf_token=([^;]+)/);
      var token = match ? match[1] : "";
      await fetch("/api/v1/auth/logout", {
        method: "POST",
        headers: { "X-CSRF-Token": token },
      });
      window.location.href = "/";
    });
  }
});
