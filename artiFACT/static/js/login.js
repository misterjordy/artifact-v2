"use strict";

document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("login-form");
  const errEl = document.getElementById("login-error");
  const submitBtn = document.getElementById("login-submit");

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    errEl.classList.add("hidden");
    submitBtn.disabled = true;
    submitBtn.textContent = "Signing in\u2026";

    try {
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: document.getElementById("username").value,
          password: document.getElementById("password").value,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        errEl.textContent = data.detail || "Login failed";
        errEl.classList.remove("hidden");
        submitBtn.disabled = false;
        submitBtn.textContent = "Sign in";
        return;
      }
      window.location.href = "/browse";
    } catch (_err) {
      errEl.textContent = "Network error — please try again";
      errEl.classList.remove("hidden");
      submitBtn.disabled = false;
      submitBtn.textContent = "Sign in";
    }
  });
});
