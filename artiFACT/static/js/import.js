/* Import pipeline UI logic. */

function importApp() {
  return {
    step: "upload",
    sessionUid: null,
    progress: 0,
    progressMessage: "",
    stagedFacts: [],
    uploadError: "",
    proposeError: "",
    doneMessage: "",

    getCsrfToken() {
      const match = document.cookie.match(/csrf_token=([^;]+)/);
      return match ? match[1] : "";
    },

    async uploadFile() {
      this.uploadError = "";
      const form = document.getElementById("upload-form");
      const formData = new FormData(form);
      const csrf = this.getCsrfToken();

      try {
        const resp = await fetch("/api/v1/import/upload", {
          method: "POST",
          headers: { "x-csrf-token": csrf },
          body: formData,
        });
        if (!resp.ok) {
          const err = await resp.json();
          this.uploadError = err.detail || "Upload failed";
          return;
        }
        const data = await resp.json();
        this.sessionUid = data.session_uid;

        const analyzeResp = await fetch(
          "/api/v1/import/analyze/" + this.sessionUid,
          {
            method: "POST",
            headers: { "x-csrf-token": csrf },
          }
        );
        if (!analyzeResp.ok) {
          const err = await analyzeResp.json();
          this.uploadError = err.detail || "Analysis trigger failed";
          return;
        }

        this.step = "analyzing";
        this.listenProgress();
      } catch (e) {
        this.uploadError = e.message || "Network error";
      }
    },

    listenProgress() {
      const source = new EventSource(
        "/api/v1/import/sessions/" + this.sessionUid + "/progress"
      );
      source.onmessage = (event) => {
        const data = JSON.parse(event.data);
        this.progress = Math.max(0, Math.min(100, data.percent));
        this.progressMessage = data.message;
        if (data.percent >= 100) {
          source.close();
          this.loadStaged();
        } else if (data.percent < 0) {
          source.close();
          this.uploadError = data.message;
          this.step = "upload";
        }
      };
      source.onerror = () => {
        source.close();
        this.loadStaged();
      };
    },

    async loadStaged() {
      try {
        const resp = await fetch(
          "/api/v1/import/sessions/" + this.sessionUid + "/staged"
        );
        if (!resp.ok) {
          this.uploadError = "Failed to load staged facts";
          this.step = "upload";
          return;
        }
        const data = await resp.json();
        this.stagedFacts = data.facts;
        this.step = "review";
      } catch (e) {
        this.uploadError = e.message;
        this.step = "upload";
      }
    },

    async proposeFacts() {
      this.proposeError = "";
      const accepted = this.stagedFacts
        .filter((f) => f.accepted)
        .map((f) => f.index);

      if (accepted.length === 0) {
        this.proposeError = "No facts selected";
        return;
      }

      const csrf = this.getCsrfToken();
      try {
        const resp = await fetch(
          "/api/v1/import/sessions/" + this.sessionUid + "/propose",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "x-csrf-token": csrf,
            },
            body: JSON.stringify({ accepted_indices: accepted }),
          }
        );
        if (!resp.ok) {
          const err = await resp.json();
          this.proposeError = err.detail || "Propose failed";
          return;
        }
        const data = await resp.json();
        this.doneMessage = data.created_count + " facts imported successfully.";
        this.step = "done";
      } catch (e) {
        this.proposeError = e.message || "Network error";
      }
    },

    async discardFacts() {
      const csrf = this.getCsrfToken();
      try {
        await fetch(
          "/api/v1/import/sessions/" + this.sessionUid + "/discard",
          {
            method: "POST",
            headers: { "x-csrf-token": csrf },
          }
        );
        this.doneMessage = "Import discarded.";
        this.step = "done";
      } catch (e) {
        this.proposeError = e.message;
      }
    },

    resetForm() {
      this.step = "upload";
      this.sessionUid = null;
      this.progress = 0;
      this.progressMessage = "";
      this.stagedFacts = [];
      this.uploadError = "";
      this.proposeError = "";
      this.doneMessage = "";
    },
  };
}
