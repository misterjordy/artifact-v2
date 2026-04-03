"use strict";

/**
 * UI state persistence via sessionStorage.
 *
 * Per-page, per-tab. Clears when the tab closes.
 * No stale junk accumulation (unlike localStorage).
 */

function loadState(key, defaults) {
  try {
    var stored = sessionStorage.getItem(key);
    if (!stored) return Object.assign({}, defaults);
    var parsed = JSON.parse(stored);
    // Merge with defaults so new fields get default values
    var result = Object.assign({}, defaults);
    for (var k in parsed) {
      if (Object.prototype.hasOwnProperty.call(parsed, k)) {
        result[k] = parsed[k];
      }
    }
    return result;
  } catch (e) {
    return Object.assign({}, defaults);
  }
}

function saveState(key, state) {
  try {
    sessionStorage.setItem(key, JSON.stringify(state));
  } catch (e) {
    // sessionStorage full or disabled — silently fail
  }
}

function clearState(key) {
  try {
    sessionStorage.removeItem(key);
  } catch (e) {
    // ignore
  }
}
