"use strict";

/**
 * Alpine.js component for the auto-approve toggle in the brand header.
 * Fetches status on init, shows confirmation popup before enabling.
 */
function autoApproveToggle() {
  return {
    eligible: false,
    active: false,
    confirming: false,
    loading: true,

    async init() {
      try {
        var res = await fetch("/api/v1/auto-approve/status", { credentials: "same-origin" });
        if (res.ok) {
          var data = await res.json();
          this.eligible = data.eligible;
          this.active = data.active;
          window.__autoApproveActive = data.active;
        }
      } catch (_) {
        // Silently fail — toggle stays hidden/off
      }
      this.loading = false;
    },

    toggle(checked) {
      if (checked) {
        // Revert checkbox immediately; wait for confirmation
        this.active = false;
        this.confirming = true;
      } else {
        this.disable();
      }
    },

    async confirmEnable() {
      this.confirming = false;
      var token = document.cookie.match(/csrf_token=([^;]+)/);
      var res = await fetch("/api/v1/auto-approve/toggle", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": token ? token[1] : "",
        },
        body: JSON.stringify({ active: true }),
      });
      if (res.ok) {
        var data = await res.json();
        this.active = data.active;
        window.__autoApproveActive = data.active;
      }
    },

    cancelConfirm() {
      this.confirming = false;
      this.active = false;
    },

    async disable() {
      var token = document.cookie.match(/csrf_token=([^;]+)/);
      var res = await fetch("/api/v1/auto-approve/toggle", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": token ? token[1] : "",
        },
        body: JSON.stringify({ active: false }),
      });
      if (res.ok) {
        this.active = false;
        window.__autoApproveActive = false;
      }
    },
  };
}
