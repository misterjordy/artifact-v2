/* Queue page Alpine.js component. */

var QUEUE_STATE_KEY = "artifact:queue:state";

// Client-side filter: hides queue cards whose text doesn't match the query
window._filterQueueItems = function (query) {
  var q = query.toLowerCase().trim();
  var cards = document.querySelectorAll("[x-data='queuePage()'] .space-y-3 > *");
  cards.forEach(function (card) {
    if (!q) {
      card.style.display = "";
      return;
    }
    var text = (card.textContent || "").toLowerCase();
    card.style.display = text.indexOf(q) >= 0 ? "" : "none";
  });
  // Persist filter
  saveState(QUEUE_STATE_KEY, {
    tab: document.querySelector("[x-data='queuePage()']") ?
      document.querySelector("[x-data='queuePage()']")._x_dataStack[0].tab : "proposals",
    filterQuery: query,
  });
};

function queuePage() {
  var saved = loadState(QUEUE_STATE_KEY, { tab: "proposals", filterQuery: "" });
  return {
    tab: saved.tab,
    proposals: [],
    moves: [],
    pendingMoves: [],
    unsigned: [],
    challenges: [],
    myChallenges: [],
    revising: false,
    reviseVersionUid: null,
    reviseOriginal: '',
    reviseSentence: '',
    reviseNote: '',
    rejectingChallenge: false,
    rejectChallengeUid: null,
    rejectChallengeProposed: '',
    rejectChallengeNote: '',

    async init() {
      var self = this;
      await this.refresh();
      setInterval(function () { self.refreshBadge(); }, 60000);

      // Restore filter input
      var filterInput = document.getElementById("queue-filter-input");
      if (filterInput && saved.filterQuery) {
        filterInput.value = saved.filterQuery;
        // Apply filter after data loads
        this.$nextTick(function () {
          window._filterQueueItems(saved.filterQuery);
        });
      }

      // Persist tab changes
      this.$watch("tab", function () {
        saveState(QUEUE_STATE_KEY, {
          tab: self.tab,
          filterQuery: filterInput ? filterInput.value : "",
        });
      });
    },

    async refresh() {
      const [pRes, mRes, pmRes, uRes, cRes, mcRes] = await Promise.all([
        fetch('/api/v1/queue/proposals', { credentials: 'same-origin' }),
        fetch('/api/v1/queue/moves', { credentials: 'same-origin' }),
        fetch('/api/v1/moves/pending', { credentials: 'same-origin' }),
        fetch('/api/v1/queue/unsigned', { credentials: 'same-origin' }),
        fetch('/api/v1/queue/challenges', { credentials: 'same-origin' }),
        fetch('/api/v1/queue/my-challenges', { credentials: 'same-origin' }),
      ]);
      if (pRes.ok) this.proposals = (await pRes.json()).data;
      if (mRes.ok) this.moves = (await mRes.json()).data;
      if (pmRes.ok) this.pendingMoves = (await pmRes.json()).data;
      if (uRes.ok) this.unsigned = (await uRes.json()).data;
      if (cRes.ok) this.challenges = (await cRes.json()).data;
      if (mcRes.ok) this.myChallenges = (await mcRes.json()).data;
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
      const total = this.proposals.length + this.moves.length + this.pendingMoves.length + this.challenges.length;
      const el = document.getElementById('nav-badge');
      if (el) el.textContent = total;
    },

    _csrf() {
      var m = document.cookie.match(/csrf_token=([^;]+)/);
      return m ? m[1] : '';
    },

    async approveVersion(uid) {
      const res = await fetch(`/api/v1/queue/approve/${uid}`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this._csrf() },
        body: '{}',
      });
      if (res.ok) await this.refresh();
    },

    async rejectVersion(uid) {
      const res = await fetch(`/api/v1/queue/reject/${uid}`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this._csrf() },
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
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this._csrf() },
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
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this._csrf() },
        body: '{}',
      });
      if (res.ok) await this.refresh();
    },

    async rejectMove(uid) {
      const res = await fetch(`/api/v1/queue/reject-move/${uid}`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this._csrf() },
        body: '{}',
      });
      if (res.ok) await this.refresh();
    },

    async approveNewMove(uid) {
      const res = await fetch(`/api/v1/moves/${uid}/approve`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this._csrf() },
        body: '{}',
      });
      if (res.ok) await this.refresh();
    },

    async rejectNewMove(uid) {
      const res = await fetch(`/api/v1/moves/${uid}/reject`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this._csrf() },
        body: '{}',
      });
      if (res.ok) await this.refresh();
    },

    async approveChallenge(uid) {
      const res = await fetch(`/api/v1/queue/approve-challenge/${uid}`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this._csrf() },
        body: '{}',
      });
      if (res.ok) await this.refresh();
    },

    openRejectChallenge(ch) {
      this.rejectChallengeUid = ch.comment_uid;
      this.rejectChallengeProposed = ch.proposed_sentence;
      this.rejectChallengeNote = '';
      this.rejectingChallenge = true;
    },

    async submitRejectChallenge() {
      const res = await fetch(`/api/v1/queue/reject-challenge/${this.rejectChallengeUid}`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this._csrf() },
        body: JSON.stringify({ note: this.rejectChallengeNote || null }),
      });
      if (res.ok) {
        this.rejectingChallenge = false;
        await this.refresh();
      }
    },
  };
}
