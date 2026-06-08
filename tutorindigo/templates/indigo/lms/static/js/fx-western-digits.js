/**
 * fx-western-digits.js
 *
 * Unifies all numerals shown on the page to Western/Latin digits (1 2 3 4 5),
 * converting Arabic-Indic (U+0660-U+0669) and Extended Arabic-Indic / Persian
 * (U+06F0-U+06F9) digits to ASCII. This covers dates rendered by edX's
 * DateUtilFactory as well as any other numbers, in any language.
 *
 * Implementation notes:
 *  - Only text nodes are touched (never attributes), so <time datetime="...">,
 *    URLs, and data-* values stay intact.
 *  - Editable / code / form-control subtrees are skipped so we never rewrite
 *    what a user is typing or literal code samples.
 *  - A MutationObserver re-runs on dynamically inserted/changed content
 *    (DateUtilFactory output, AJAX course lists, etc.). Re-converting already
 *    converted text is a no-op, so the observer cannot loop.
 */
(function () {
  "use strict";

  // Non-global for cheap test(); global for replace().
  var HAS_ARABIC_DIGIT = /[٠-٩۰-۹]/;
  var ARABIC_DIGIT_GLOBAL = /[٠-٩۰-۹]/g;

  function toWestern(str) {
    return str.replace(ARABIC_DIGIT_GLOBAL, function (ch) {
      var code = ch.charCodeAt(0);
      // Arabic-Indic 0x0660-0x0669, Extended (Persian) 0x06F0-0x06F9.
      return code <= 0x0669
        ? String(code - 0x0660)
        : String(code - 0x06F0);
    });
  }

  // Element tags whose text must not be altered.
  var SKIP_TAGS = {
    SCRIPT: true, STYLE: true, TEXTAREA: true, INPUT: true,
    SELECT: true, OPTION: true, CODE: true, PRE: true,
    KBD: true, SAMP: true
  };

  function isSkipped(textNode) {
    var el = textNode.parentNode;
    while (el && el.nodeType === 1) {
      if (SKIP_TAGS[el.tagName]) return true;
      if (el.isContentEditable) return true;
      el = el.parentNode;
    }
    return false;
  }

  function convertTextNode(node) {
    var value = node.nodeValue;
    if (!value || !HAS_ARABIC_DIGIT.test(value)) return;
    if (isSkipped(node)) return;
    node.nodeValue = toWestern(value);
  }

  function convertSubtree(root) {
    if (!root) return;
    if (root.nodeType === 3) { // Text node
      convertTextNode(root);
      return;
    }
    if (root.nodeType !== 1 && root.nodeType !== 9) return; // Element or Document
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
    var pending = [];
    var n;
    while ((n = walker.nextNode())) pending.push(n);
    for (var i = 0; i < pending.length; i++) convertTextNode(pending[i]);
  }

  function run() {
    convertSubtree(document.body);

    if (!window.MutationObserver) return;
    var observer = new MutationObserver(function (mutations) {
      for (var i = 0; i < mutations.length; i++) {
        var m = mutations[i];
        if (m.type === "characterData") {
          convertTextNode(m.target);
        } else if (m.addedNodes && m.addedNodes.length) {
          for (var j = 0; j < m.addedNodes.length; j++) {
            convertSubtree(m.addedNodes[j]);
          }
        }
      }
    });
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
