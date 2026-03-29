/* Queue page Alpine.js component. */

function queuePage() {
  return {
    tab: 'proposals',
    proposals: [],
    moves: [],
    unsigned: [],
    revising: false,
    reviseVersionUid: null,
    reviseOriginal: '',
    reviseSentence: '',
    reviseNote: '',

    async init() {
      await this.refresh();
      setInterval(() => this.refreshBadge(), 60000);
    },

    async refresh() {
      const [pRes, mRes, uRes] = await Promise.all([
        fetch('/api/v1/queue/proposals', { credentials: 'same-origin' }),
        fetch('/api/v1/queue/moves', { credentials: 'same-origin' }),
        fetch('/api/v1/queue/unsigned', { credentials: 'same-origin' }),
      ]);
      if (pRes.ok) this.proposals = (await pRes.json()).data;
      if (mRes.ok) this.moves = (await mRes.json()).data;
      if (uRes.ok) this.unsigned = (await uRes.json()).data;
      this.updateNavBadge();
    },

    async refreshBadge() {
      const res = await fetch('/api/v1/queue/counts', { credentials: 'same-origin' });
      if (res.ok) {
        const data = await res.json();
        const el = document.getElementById('nav-badge');
        if (el) el.textContent = data.total;
      }
    },

    updateNavBadge() {
      const total = this.proposals.length + this.moves.length;
      const el = document.getElementById('nav-badge');
      if (el) el.textContent = total;
    },

    async approveVersion(uid) {
      const res = await fetch(`/api/v1/queue/approve/${uid}`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      if (res.ok) await this.refresh();
    },

    async rejectVersion(uid) {
      const res = await fetch(`/api/v1/queue/reject/${uid}`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      if (res.ok) await this.refresh();
    },

    openRevise(p) {
      this.reviseVersionUid = p.version_uid;
      this.reviseOriginal = p.display_sentence;
      this.reviseSentence = p.display_sentence;
      this.reviseNote = '';
      this.revising = true;
    },

    async submitRevise() {
      const res = await fetch(`/api/v1/queue/revise/${this.reviseVersionUid}`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          revised_sentence: this.reviseSentence,
          note: this.reviseNote || null,
        }),
      });
      if (res.ok) {
        this.revising = false;
        await this.refresh();
      }
    },

    async approveMove(uid) {
      const res = await fetch(`/api/v1/queue/approve-move/${uid}`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      if (res.ok) await this.refresh();
    },

    async rejectMove(uid) {
      const res = await fetch(`/api/v1/queue/reject-move/${uid}`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      if (res.ok) await this.refresh();
    },
  };
}
