function exportPage() {
  return {
    factsheetNodeUid: '',
    factsheetFormat: 'json',
    docgenNodeUid: '',
    docgenTemplateUid: '',
    viewsNodeUid: '',
    viewsTemplateUid: '',
    templates: [],
    generating: false,
    docReady: false,
    progress: 0,
    progressStage: '',
    downloadUrl: null,
    viewsResult: null,

    async init() {
      const csrf = document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
      try {
        const res = await fetch('/api/v1/export/templates', {
          headers: { 'x-csrf-token': csrf }
        });
        if (res.ok) {
          this.templates = await res.json();
          if (this.templates.length > 0) {
            this.docgenTemplateUid = this.templates[0].template_uid;
            this.viewsTemplateUid = this.templates[0].template_uid;
          }
        }
      } catch (e) {
        console.error('Failed to load templates', e);
      }
    },

    downloadFactsheet() {
      if (!this.factsheetNodeUid) return;
      const params = new URLSearchParams({
        node_uids: this.factsheetNodeUid,
        format: this.factsheetFormat,
        state: 'published'
      });
      window.location.href = '/api/v1/export/factsheet?' + params.toString();
    },

    async generateDocument() {
      if (!this.docgenNodeUid || !this.docgenTemplateUid) return;
      this.generating = true;
      this.progress = 0;
      this.progressStage = 'Starting...';
      this.downloadUrl = null;
      this.docReady = false;

      const csrf = document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
      try {
        const res = await fetch('/api/v1/export/document', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'x-csrf-token': csrf
          },
          body: JSON.stringify({
            node_uids: [this.docgenNodeUid],
            template_uid: this.docgenTemplateUid
          })
        });
        if (!res.ok) {
          this.generating = false;
          return;
        }
        const data = await res.json();

        const evtSource = new EventSource(
          '/api/v1/export/document/' + data.session_uid + '/progress'
        );
        evtSource.onmessage = (event) => {
          const d = JSON.parse(event.data);
          this.progress = d.percent || 0;
          this.progressStage = d.stage || '';
          if (d.download_url) {
            this.downloadUrl = d.download_url;
            this.docReady = true;
            this.generating = false;
            evtSource.close();
          }
          if (d.percent >= 100) {
            this.generating = false;
            evtSource.close();
          }
        };
        evtSource.onerror = () => {
          this.generating = false;
          evtSource.close();
        };
      } catch (e) {
        this.generating = false;
      }
    },

    async runPreview() {
      if (!this.viewsNodeUid || !this.viewsTemplateUid) return;
      const csrf = document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
      try {
        const res = await fetch('/api/v1/export/views', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'x-csrf-token': csrf
          },
          body: JSON.stringify({
            node_uids: [this.viewsNodeUid],
            template_uid: this.viewsTemplateUid
          })
        });
        if (res.ok) {
          this.viewsResult = await res.json();
        }
      } catch (e) {
        console.error('Preview failed', e);
      }
    }
  };
}
