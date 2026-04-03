"use strict";

/**
 * Site-wide acronym tooltips.
 *
 * Loads the full acronym dict once, then applies dotted underlines
 * and hover tooltips to matching text in .fact-text elements.
 */
(function () {
    var acronymDict = null;
    var loaded = false;
    var pattern = null;

    function loadAcronyms() {
        if (loaded) return Promise.resolve();
        return fetch("/api/v1/acronyms/all")
            .then(function (resp) {
                if (!resp.ok) throw new Error("HTTP " + resp.status);
                return resp.json();
            })
            .then(function (data) {
                acronymDict = data.data.acronyms;
                loaded = true;
                pattern = buildPattern(acronymDict);
            })
            .catch(function () {
                acronymDict = {};
                loaded = true;
            });
    }

    function buildPattern(dict) {
        var keys = Object.keys(dict).sort(function (a, b) {
            return b.length - a.length;
        });
        if (keys.length === 0) return null;
        var escaped = keys.map(function (k) {
            return k.replace(/[.*+?^${}()|[\]\\\/]/g, "\\$&");
        });
        return new RegExp("\\b(" + escaped.join("|") + ")\\b", "g");
    }

    function applyTooltips(container) {
        if (!acronymDict || !pattern) return;

        var elements = (container || document).querySelectorAll(
            ".fact-text:not([data-acronyms-processed])"
        );

        elements.forEach(function (el) {
            el.setAttribute("data-acronyms-processed", "true");

            var walker = document.createTreeWalker(
                el,
                NodeFilter.SHOW_TEXT,
                null,
                false
            );

            var textNodes = [];
            while (walker.nextNode()) {
                textNodes.push(walker.currentNode);
            }

            textNodes.forEach(function (textNode) {
                var text = textNode.textContent;
                pattern.lastIndex = 0;
                if (!pattern.test(text)) return;
                pattern.lastIndex = 0;

                var fragment = document.createDocumentFragment();
                var lastIdx = 0;
                var match;

                while ((match = pattern.exec(text)) !== null) {
                    if (match.index > lastIdx) {
                        fragment.appendChild(
                            document.createTextNode(
                                text.slice(lastIdx, match.index)
                            )
                        );
                    }

                    var abbr = document.createElement("abbr");
                    abbr.textContent = match[0];
                    abbr.className = "acronym-tooltip";

                    var expansions = acronymDict[match[0]];
                    if (expansions) {
                        abbr.title = expansions.join(" · ");
                    }

                    fragment.appendChild(abbr);
                    lastIdx = pattern.lastIndex;
                }

                if (lastIdx < text.length) {
                    fragment.appendChild(
                        document.createTextNode(text.slice(lastIdx))
                    );
                }

                textNode.parentNode.replaceChild(fragment, textNode);
            });
        });
    }

    function init() {
        loadAcronyms().then(function () {
            applyTooltips();
        });

        document.addEventListener("htmx:afterSwap", function () {
            setTimeout(function () { applyTooltips(); }, 50);
        });

        var main = document.querySelector("main") || document.body;
        var observer = new MutationObserver(function () {
            applyTooltips();
        });
        observer.observe(main, { childList: true, subtree: true });

        document.addEventListener("acronyms-changed", function () {
            loaded = false;
            pattern = null;
            loadAcronyms().then(function () {
                document
                    .querySelectorAll("[data-acronyms-processed]")
                    .forEach(function (el) {
                        el.removeAttribute("data-acronyms-processed");
                    });
                applyTooltips();
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
