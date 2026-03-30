"use strict";

/**
 * Smart sentence truncation — keeps first and last words visible.
 * @param {string} sentence
 * @param {number} maxChars
 * @returns {string}
 */
function truncateSentence(sentence, maxChars) {
  if (!sentence) return "";
  if (sentence.length <= maxChars) return sentence;

  var words = sentence.split(/\s+/);
  if (words.length <= 2) return sentence.slice(0, maxChars - 1) + "\u2026";

  var first = [];
  var last = [];
  var i = 0;
  var j = words.length - 1;

  while (i <= j) {
    first.push(words[i]);
    var candidate = first.join(" ") + " \u2026" + (last.length ? " " + last.join(" ") : "");
    if (candidate.length > maxChars && first.length > 1) {
      first.pop();
      break;
    }
    i++;

    if (i > j) break;

    last.unshift(words[j]);
    var candidate2 = first.join(" ") + " \u2026 " + last.join(" ");
    if (candidate2.length > maxChars && last.length > 1) {
      last.shift();
      break;
    }
    j--;
  }

  if (last.length === 0) {
    return first.join(" ") + " \u2026";
  }
  return first.join(" ") + " \u2026 " + last.join(" ");
}
