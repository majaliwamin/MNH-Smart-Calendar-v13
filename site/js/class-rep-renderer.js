(function () {
  "use strict";

  // Common academic/statistical shorthand accepted by KaTeX. The model is
  // instructed to use standard LaTeX, but these aliases make short replies
  // such as \chisq or \pval render as conventional notation as well.
  var STATS_MACROS = {
    "\\chisq": "\\chi^2",
    "\\ChiSq": "\\chi^2",
    "\\hnull": "H_0",
    "\\halt": "H_a",
    "\\pval": "p\\text{-value}",
    "\\E": "\\operatorname{E}",
    "\\Var": "\\operatorname{Var}",
    "\\SD": "\\operatorname{SD}",
    "\\SE": "\\operatorname{SE}",
    "\\Pr": "\\Pr"
  };

  // Notations that phones sometimes render with a missing glyph when a model
  // writes them as plain Unicode. Wrapping them in math delimiters lets KaTeX
  // draw them with the bundled fonts on both mobile and desktop.
  var UNICODE_LATEX = {
    "α":"\\alpha", "β":"\\beta", "γ":"\\gamma", "δ":"\\delta", "ε":"\\varepsilon",
    "ζ":"\\zeta", "η":"\\eta", "θ":"\\theta", "ι":"\\iota", "κ":"\\kappa",
    "λ":"\\lambda", "μ":"\\mu", "ν":"\\nu", "ξ":"\\xi", "π":"\\pi",
    "ρ":"\\rho", "σ":"\\sigma", "τ":"\\tau", "υ":"\\upsilon", "φ":"\\phi",
    "χ":"\\chi", "ψ":"\\psi", "ω":"\\omega", "Γ":"\\Gamma", "Δ":"\\Delta",
    "Θ":"\\Theta", "Λ":"\\Lambda", "Ξ":"\\Xi", "Π":"\\Pi", "Σ":"\\sum",
    "Φ":"\\Phi", "Ψ":"\\Psi", "Ω":"\\Omega", "∞":"\\infty", "≤":"\\le",
    "≥":"\\ge", "≠":"\\ne", "≈":"\\approx", "≡":"\\equiv", "±":"\\pm",
    "×":"\\times", "÷":"\\div", "∑":"\\sum", "∏":"\\prod", "∫":"\\int",
    "→":"\\to", "←":"\\leftarrow", "↔":"\\leftrightarrow", "∈":"\\in",
    "∉":"\\notin", "⊂":"\\subset", "⊆":"\\subseteq", "∪":"\\cup",
    "∩":"\\cap", "∅":"\\emptyset", "∂":"\\partial", "∇":"\\nabla",
    "∝":"\\propto", "ℝ":"\\mathbb{R}", "ℤ":"\\mathbb{Z}", "ℕ":"\\mathbb{N}",
    "ℚ":"\\mathbb{Q}", "ℂ":"\\mathbb{C}"
  };
  var SUPERSCRIPT_DIGITS = {"⁰":"0", "¹":"1", "²":"2", "³":"3", "⁴":"4", "⁵":"5", "⁶":"6", "⁷":"7", "⁸":"8", "⁹":"9"};
  var SUBSCRIPT_DIGITS = {"₀":"0", "₁":"1", "₂":"2", "₃":"3", "₄":"4", "₅":"5", "₆":"6", "₇":"7", "₈":"8", "₉":"9"};

  function latexForSymbol(symbol) {
    return UNICODE_LATEX[symbol] || symbol;
  }

  function unicodeDigits(value, table) {
    return String(value).split("").map(function (digit) { return table[digit] || digit; }).join("");
  }

  function wrapLatex(expression) {
    return "\\(" + expression + "\\)";
  }

  function esc(value) {
    return String(value).replace(/[&<>"']/g, function (c) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
    });
  }

  function count(text, pattern) {
    var matches = String(text).match(pattern);
    return matches ? matches.length : 0;
  }

  // Repair the malformed delimiters language models commonly emit: doubled
  // backslashes, dollar delimiters, bare bracket equations, stray '$' inside a
  // formula and inline delimiters nested inside display math. Fenced code is
  // never touched.
  function repairProse(text) {
    var out = String(text);
    out = out.replace(/\\{2,}/g, "\\");
    out = out.replace(/\$\$([\s\S]+?)\$\$/g, function (_, equation) {
      return "\\[" + equation.trim() + "\\]";
    });
    out = out.replace(/(^|[^\\])\$([^$\n]+)\$/g, function (whole, prefix, equation) {
      return /[\\=^_{}]/.test(equation)
        ? prefix + "\\(" + equation.trim() + "\\)"
        : whole;
    });
    out = out.replace(/\[\s*([^\[\]\n]*(?:\\[A-Za-z]+|[=^_])[^\[\]\n]*)\s\]/g, function (_, equation) {
      return "\\[" + equation.trim() + "\\]";
    });
    out = out.replace(/\(\s*(?:\(((?:\\[^()]+|[A-Za-z][A-Za-z0-9_{}^+\-*/= ]*))\)|(\\[^()]+))\s*\)/g, function (_, doubled, single) {
      return "\\(" + (doubled || single).trim() + "\\)";
    });
    out = out.replace(/(\\\([\s\S]*?)(\\\))/g, function (_, body, close) {
      return body.replace(/\$/g, "") + close;
    });
    out = out.replace(/(\\\[[\s\S]*?)(\\\])/g, function (_, body, close) {
      return body.replace(/\$/g, "") + close;
    });
    out = out.replace(/\\\[([\s\S]*?)\\\]/g, function (_, body) {
      return "\\[" + body.replace(/\\\(([\s\S]*?)\\\)/g, "$1") + "\\]";
    });
    var pairs = [["\\[", "\\]"], ["\\(", "\\)"]];
    pairs.forEach(function (pair) {
      var open = count(out, new RegExp(pair[0].replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g"));
      var close = count(out, new RegExp(pair[1].replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g"));
      if (open > close) out += "\n" + new Array(open - close + 1).join(pair[1]);
      while (close > open) {
        var at = out.lastIndexOf(pair[1]);
        if (at < 0) break;
        out = out.slice(0, at) + out.slice(at + 2);
        close -= 1;
      }
    });
    // Escape pipes only where they are literal content, so Markdown tables are
    // not broken by the repair pass.
    return out.replace(/\\\|/g, "|").replace(/\\{2,}/g, "\\");
  }

  // Existing math, dollars and inline code are already safe. Only prose is
  // scanned so a symbol inside a formula or code sample is never wrapped twice.
  function wrapProseNotation(text) {
    var out = String(text);
    out = out.replace(/(χ)\s*(²|2)/g, function () {
      return wrapLatex("\\chi^2");
    });
    out = out.replace(/([αβγδθελμπρστφχψωΔΣΩ])\s*(=|≤|≥|≠|≈)\s*([-+]?\d+(?:\.\d+)?%?)/g, function (_, symbol, operator, number) {
      return wrapLatex(latexForSymbol(symbol) + " " + latexForSymbol(operator) + " " + number.replace("%", "\\%"));
    });
    out = out.replace(/([A-Za-z])([\u0304\u0303\u0302])/g, function (_, letter, mark) {
      var command = mark === "\u0304" ? "\\bar" : mark === "\u0303" ? "\\tilde" : "\\hat";
      return wrapLatex(command + "{" + letter + "}");
    });
    out = out.replace(/([A-Za-z)])([⁰¹²³⁴⁵⁶⁷⁸⁹]+)/g, function (_, base, digits) {
      return wrapLatex(base + "^" + unicodeDigits(digits, SUPERSCRIPT_DIGITS));
    });
    out = out.replace(/([A-Za-z)])([₀₁₂₃₄₅₆₇₈₉]+)/g, function (_, base, digits) {
      return wrapLatex(base + "_" + unicodeDigits(digits, SUBSCRIPT_DIGITS));
    });
    out = out.replace(/√\s*([A-Za-z0-9]+|\([^)]+\))/g, function (_, radicand) {
      return wrapLatex("\\sqrt{" + radicand.replace(/^\(|\)$/g, "") + "}");
    });
    out = out.replace(/([αβγδεζηθικλμνξοπρστυφχψωΓΔΘΛΞΠΣΦΨΩ∞≤≥≠≈≡±×÷∑∏∫→←↔∈∉⊂⊆∪∩∅∂∇∝ℝℤℕℚℂ])/g, function (_, symbol) {
      return wrapLatex(latexForSymbol(symbol));
    });
    return out;
  }

  function wrapUnicodeNotation(text) {
    var protectedPattern = /(\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]|\$[\s\S]*?\$|`[^`]*`)/g;
    return String(text).split(protectedPattern).map(function (part) {
      if (!part || /^(\\\(|\\\[|\$|`)/.test(part)) return part;
      return wrapProseNotation(part);
    }).join("");
  }

  function repairMath(source) {
    return String(source).split(/(```[\s\S]*?```|~~~[\s\S]*?~~~)/g).map(function (part) {
      return /^\s*(```|~~~)/.test(part) ? part : wrapUnicodeNotation(repairProse(part));
    }).join("");
  }

  function plainMath(expression, display) {
    var text = String(expression)
      .replace(/\\(?:left|right)\b/g, "")
      .replace(/\\text\{([^}]*)\}/g, "$1")
      .replace(/\\operatorname\{([^}]*)\}/g, "$1")
      .replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, "($1)/($2)")
      .replace(/\\dfrac\{([^{}]+)\}\{([^{}]+)\}/g, "($1)/($2)")
      .replace(/\\sqrt\{([^{}]+)\}/g, "√($1)")
      .replace(/\\(?:bar|overline)\{([^}]+)\}/g, "$1̄")
      .replace(/\\hat\{([^}]+)\}/g, "$1̂")
      .replace(/\\tilde\{([^}]+)\}/g, "$1̃")
      .replace(/\\mathbb\{([A-Za-z])\}/g, function (_, letter) {
        return ({"R":"ℝ", "Z":"ℤ", "N":"ℕ", "Q":"ℚ", "C":"ℂ"})[letter] || letter;
      })
      .replace(/\\sum/g, "Σ").replace(/\\prod/g, "∏").replace(/\\int/g, "∫")
      .replace(/\\times/g, "×").replace(/\\div/g, "÷").replace(/\\pm/g, "±")
      .replace(/\\le\b/g, "≤").replace(/\\ge\b/g, "≥").replace(/\\ne\b/g, "≠").replace(/\\neq/g, "≠")
      .replace(/\\approx/g, "≈").replace(/\\equiv/g, "≡").replace(/\\to\b/g, "→").replace(/\\rightarrow\b/g, "→")
      .replace(/\\in\b/g, "∈").replace(/\\cup/g, "∪").replace(/\\cap/g, "∩").replace(/\\emptyset/g, "∅")
      .replace(/\\alpha/g, "α").replace(/\\beta/g, "β").replace(/\\gamma/g, "γ").replace(/\\delta/g, "δ")
      .replace(/\\theta/g, "θ").replace(/\\lambda/g, "λ").replace(/\\mu/g, "μ")
      .replace(/\\sigma/g, "σ").replace(/\\chi/g, "χ").replace(/\\pi/g, "π")
      .replace(/\\infty/g, "∞").replace(/\\quad/g, "  ").replace(/\\,/g, " ")
      .replace(/\^\{([^}]+)\}|\^([A-Za-z0-9])/g, function (_, braced, single) {
        var value = braced || single || "";
        return /^\d+$/.test(value) ? unicodeDigits(value, SUPERSCRIPT_DIGITS) : "^(" + value + ")";
      })
      .replace(/_\{([^}]+)\}|_([A-Za-z0-9])/g, function (_, braced, single) {
        var value = braced || single || "";
        return /^\d+$/.test(value) ? unicodeDigits(value, SUBSCRIPT_DIGITS) : "_(" + value + ")";
      })
      .replace(/[{}]/g, "")
      .replace(/\\/g, "")
      .replace(/\s+/g, " ")
      .trim();
    return display ? "  " + text + "  " : text;
  }

  // Last-resort renderer for devices where KaTeX cannot load: show readable
  // Unicode notation instead of raw backslash commands.
  function renderPlainMath(bubble) {
    var walker = document.createTreeWalker(bubble, NodeFilter.SHOW_TEXT, null);
    var nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(function (node) {
      var text = node.nodeValue;
      var pattern = /\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)/g;
      var match, last = 0, fragment = document.createDocumentFragment();
      while ((match = pattern.exec(text)) !== null) {
        if (match.index > last) fragment.append(document.createTextNode(text.slice(last, match.index)));
        var span = document.createElement("span");
        span.className = "cr-math-fallback";
        span.textContent = plainMath(match[1] || match[2], Boolean(match[1]));
        fragment.append(span);
        last = pattern.lastIndex;
      }
      if (last && last < text.length) fragment.append(document.createTextNode(text.slice(last)));
      if (last) node.parentNode.replaceChild(fragment, node);
    });
  }

  function valid(c) {
    var t = String(c.type || c.chartType || "").toLowerCase();
    if (["bar","line","pie","doughnut","scatter"].indexOf(t) < 0) return false;
    if (!Array.isArray(c.datasets) || !c.datasets.length || c.datasets.length > 8) return false;
    if (t === "scatter") return c.datasets.every(function (d) {
      return d && Array.isArray(d.data) && d.data.length > 0 && d.data.length <= 100 &&
        d.data.every(function (p) { return p && Number.isFinite(Number(p.x)) && Number.isFinite(Number(p.y)); });
    });
    return Array.isArray(c.labels) && c.labels.length > 0 && c.labels.length <= 24 &&
      c.datasets.every(function (d) {
        return d && Array.isArray(d.data) && d.data.length === c.labels.length &&
          d.data.every(function (n) { return Number.isFinite(Number(n)); });
      });
  }

  function chart(slot, c) {
    var type = String(c.type || c.chartType).toLowerCase();
    var fig = document.createElement("figure");
    fig.className = "cr-chart-figure";
    if (c.title) {
      var cap = document.createElement("figcaption");
      cap.className = "cr-chart-title";
      cap.textContent = String(c.title).slice(0, 180);
      fig.append(cap);
    }
    if (!window.Chart) {
      var fallback = document.createElement("p");
      fallback.className = "cr-chart-fallback";
      fallback.textContent = "Chart data: " + c.datasets.map(function (d) {
        return String(d.label || "Series") + ": " + d.data.map(function (n, i) {
          return type === "scatter" ? "(" + n.x + ", " + n.y + ")" : c.labels[i] + " " + n;
        }).join(", ");
      }).join("; ");
      fig.append(fallback);
      slot.replaceWith(fig);
      return;
    }
    var frame = document.createElement("div");
    frame.className = "cr-chart-frame";
    var canvas = document.createElement("canvas");
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", String(c.title || "Chart") + ". Data values are available in the chart data table.");
    frame.append(canvas);
    fig.append(frame);
    var details = document.createElement("details");
    details.className = "cr-chart-data";
    var summary = document.createElement("summary");
    summary.textContent = "View chart data";
    details.append(summary);
    var table = document.createElement("table");
    var head = document.createElement("tr");
    var first = document.createElement("th");
    first.textContent = type === "scatter" ? "Series" : "Category";
    head.append(first);
    c.datasets.forEach(function (d) { var th = document.createElement("th"); th.textContent = d.label || "Series"; head.append(th); });
    var thead = document.createElement("thead"); thead.append(head); table.append(thead);
    var tbody = document.createElement("tbody");
    if (type === "scatter") {
      c.datasets.forEach(function (d) { d.data.forEach(function (p, i) {
        var row = document.createElement("tr"), name = document.createElement("th"), val = document.createElement("td");
        name.textContent = String(d.label || "Series") + " " + (i + 1); val.textContent = "x: " + p.x + ", y: " + p.y; row.append(name, val); tbody.append(row);
      }); });
    } else {
      c.labels.forEach(function (label, i) {
        var row = document.createElement("tr"), name = document.createElement("th");
        name.textContent = String(label); row.append(name);
        c.datasets.forEach(function (d) { var td = document.createElement("td"); td.textContent = String(d.data[i]); row.append(td); });
        tbody.append(row);
      });
    }
    table.append(tbody);
    var wrap = document.createElement("div"); wrap.className = "cr-table-wrap"; wrap.append(table);
    details.append(wrap); fig.append(details); slot.replaceWith(fig);
    var colors = ["#16a6a1","#e5a13b","#7b72d8","#d56b83","#4d91c6","#87a84b","#bd83d5","#d17d45"];
    var sets = c.datasets.map(function (d, i) {
      var out = Object.assign({}, d), color = colors[i % colors.length];
      if (type === "pie" || type === "doughnut") { out.backgroundColor = c.labels.map(function (_, j) { return colors[j % colors.length]; }); out.borderColor = "#172235"; out.borderWidth = 2; }
      else { out.borderColor = color; out.backgroundColor = type === "line" ? color + "33" : color; out.borderWidth = type === "line" ? 2.5 : 1; if (type === "line") { out.fill = false; out.tension = 0.25; } }
      return out;
    });
    try {
      new window.Chart(canvas.getContext("2d"), {
        type: type, data: {labels: c.labels || [], datasets: sets},
        options: {responsive: true, maintainAspectRatio: false,
          plugins: {legend: {position: "bottom", labels: {color: "#dce4ef", usePointStyle: true}}, title: {display: false}},
          scales: (type === "pie" || type === "doughnut") ? {} : {
            x: {ticks: {color: "#b9c5d5"}, grid: {color: "rgba(150,170,195,.12)"}},
            y: {beginAtZero: true, ticks: {color: "#b9c5d5"}, grid: {color: "rgba(150,170,195,.12)"}}
          }}
      });
    } catch (_) { frame.remove(); }
  }

  function render(bubble, value, transcript) {
    var source = repairMath(value);
    if (!window.marked || !window.DOMPurify) {
      bubble.textContent = source;
      return;
    }
    // Marked treats \[ and \( as Markdown escapes. Shield the repaired
    // delimiters during Markdown parsing, restore them once, then sanitise.
    var mathDelimiters = [];
    source = source.replace(/\\\[|\\\]|\\\(|\\\)/g, function (delimiter) {
      var token = "CRARAMATHDELIMITER" + mathDelimiters.length + "TOKEN";
      mathDelimiters.push({token: token, delimiter: delimiter});
      return token;
    });
    var charts = [];
    var renderer = new window.marked.Renderer();
    renderer.code = function (token) {
      var lang = String(token.lang || "").toLowerCase();
      if (lang === "chart" || lang === "chart-json") {
        try { var c = JSON.parse(token.text); if (valid(c)) { var i = charts.push(c) - 1; return '<div class="cr-chart-slot" data-chart-slot="' + i + '"></div>'; } } catch (_) {}
      }
      return "<pre><code>" + esc(token.text) + "</code></pre>";
    };
    var html = window.marked.parse(source, {gfm: true, renderer: renderer});
    mathDelimiters.forEach(function (item) {
      html = html.split(item.token).join(item.delimiter);
    });
    bubble.innerHTML = window.DOMPurify.sanitize(html, {USE_PROFILES: {html: true}, ADD_ATTR: ["class","data-chart-slot"]});
    bubble.querySelectorAll("[data-chart-slot]").forEach(function (slot) {
      var i = Number(slot.getAttribute("data-chart-slot"));
      if (Number.isInteger(i) && charts[i]) chart(slot, charts[i]);
    });
    if (window.katex && window.renderMathInElement) {
      try {
        window.renderMathInElement(bubble, {
          delimiters: [
            {left: "$$", right: "$$", display: true},
            {left: "\\[", right: "\\]", display: true},
            {left: "\\(", right: "\\)", display: false},
            {left: "$", right: "$", display: false}
          ],
          macros: STATS_MACROS,
          throwOnError: false,
          strict: "ignore",
          trust: false
        });
      } catch (_) {
        renderPlainMath(bubble);
      }
    } else {
      renderPlainMath(bubble);
    }
    if (transcript) transcript.scrollTop = transcript.scrollHeight;
  }

  window.CRARAResponseRenderer = {render: render, repairMath: repairMath, plainMath: plainMath};
})();
