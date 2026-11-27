(function () {
  "use strict";

  var EXTENSION_ATTRS = [
    "data-gr-ext-installed",
    "data-new-gr-c-s-check-loaded",
    "data-gr-c-s-loaded",
    "data-grammarly-shadow-root",
    "data-gramm"
  ];

  var EXTENSION_SELECTORS = [
    "grammarly-desktop-integration",
    "grammarly-extension",
    "grammarly-popups",
    "[data-grammarly-shadow-root]",
    "iframe[src*='grammarly']",
    "[data-gr-ext-installed]",
    "[data-new-gr-c-s-check-loaded]"
  ];

  function markDisabled(root) {
    if (!root || !root.setAttribute) return;
    try {
      root.setAttribute("data-gramm", "false");
      root.setAttribute("data-gramm_editor", "false");
      root.setAttribute("data-enable-grammarly", "false");
      root.setAttribute("data-grammarly", "false");
    } catch (_) {}
  }

  function scrubNode(node) {
    if (!node) return;
    try {
      if (node.nodeType === 1) {
        var tag = (node.tagName || "").toLowerCase();
        if (tag.indexOf("grammarly") === 0) {
          node.remove();
          return;
        }
        for (var i = 0; i < EXTENSION_ATTRS.length; i++) {
          if (node.hasAttribute && node.hasAttribute(EXTENSION_ATTRS[i])) {
            node.removeAttribute(EXTENSION_ATTRS[i]);
          }
        }
        if (node.matches && EXTENSION_SELECTORS.some(function (sel) { try { return node.matches(sel); } catch (_) { return false; } })) {
          node.remove();
          return;
        }
      }
    } catch (_) {}
  }

  function scrubTree(root) {
    if (!root || !root.querySelectorAll) return;
    markDisabled(root.documentElement || root);
    markDisabled(root.body || root);
    try {
      var nodes = root.querySelectorAll(EXTENSION_SELECTORS.join(","));
      for (var i = 0; i < nodes.length; i++) scrubNode(nodes[i]);
    } catch (_) {}
    try {
      var all = root.querySelectorAll("[data-gr-ext-installed],[data-new-gr-c-s-check-loaded],[data-gr-c-s-loaded],[data-grammarly-shadow-root]");
      for (var j = 0; j < all.length; j++) scrubNode(all[j]);
    } catch (_) {}
  }

  function isExtensionNoise(args) {
    try {
      var text = Array.prototype.map.call(args || [], function (a) {
        if (typeof a === "string") return a;
        if (a && a.message) return String(a.message);
        return "";
      }).join(" ");
      return /grammarly|permissions policy violation: unload/i.test(text);
    } catch (_) {
      return false;
    }
  }

  function wrapConsole(method) {
    var original = console[method];
    if (typeof original !== "function") return;
    console[method] = function () {
      if (isExtensionNoise(arguments)) return;
      return original.apply(console, arguments);
    };
  }

  wrapConsole("error");
  wrapConsole("warn");
  wrapConsole("log");

  try {
    window.addEventListener("error", function (event) {
      var msg = String((event && (event.message || (event.error && event.error.message))) || "");
      var src = String((event && event.filename) || "");
      if (/grammarly/i.test(msg) || /grammarly/i.test(src)) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    }, true);
    window.addEventListener("unhandledrejection", function (event) {
      var reason = event && event.reason;
      var msg = String((reason && (reason.message || reason)) || "");
      if (/grammarly/i.test(msg)) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    }, true);
  } catch (_) {}

  function installObserver() {
    try {
      if (!window.MutationObserver || !document.documentElement) return;
      scrubTree(document);
      var obs = new MutationObserver(function (mutations) {
        for (var i = 0; i < mutations.length; i++) {
          var m = mutations[i];
          if (m.type === "attributes") {
            scrubNode(m.target);
          }
          var added = m.addedNodes || [];
          for (var j = 0; j < added.length; j++) {
            scrubNode(added[j]);
            if (added[j] && added[j].querySelectorAll) scrubTree(added[j]);
          }
        }
      });
      obs.observe(document.documentElement, {
        subtree: true,
        childList: true,
        attributes: true,
        attributeFilter: EXTENSION_ATTRS
      });
    } catch (_) {}
  }

  markDisabled(document.documentElement);
  if (document.body) markDisabled(document.body);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", installObserver, { once: true });
  } else {
    installObserver();
  }
})();