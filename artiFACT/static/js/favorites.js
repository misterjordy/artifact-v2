"use strict";

/**
 * Favorites system — star nodes in the taxonomy tree.
 * Stores [{uid, title, breadcrumb}, ...] in localStorage('artifact-favorites').
 * Uses Alpine.store('favorites') for reactivity.
 */
document.addEventListener("alpine:init", function () {
  var STORAGE_KEY = "artifact-favorites";

  function loadFavorites() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    } catch (_) {
      return [];
    }
  }

  function saveFavorites(favs) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(favs));
  }

  Alpine.store("favorites", {
    items: loadFavorites(),

    isFavorite: function (uid) {
      return this.items.some(function (f) { return f.uid === uid; });
    },

    toggle: function (uid, title, breadcrumb) {
      if (this.isFavorite(uid)) {
        this.items = this.items.filter(function (f) { return f.uid !== uid; });
      } else {
        this.items.push({ uid: uid, title: title, breadcrumb: breadcrumb || "" });
      }
      saveFavorites(this.items);
    },

    remove: function (uid) {
      this.items = this.items.filter(function (f) { return f.uid !== uid; });
      saveFavorites(this.items);
    }
  });
});
