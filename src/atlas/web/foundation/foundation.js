/* Atlas UI foundation (session B0): events, behaviours and small helpers shared by every screen.
   Depends on theme-boot.js (window.atlasTheme). No network requests. Plain ES5 so it runs in every browser we support.

   Events (all on document, payload in event.detail). Listen with atlas.on(name, fn(detail, event)).
     atlas:open-report   {placeId, region}   Report tab and the place-card Report button.  Owner of the listener: B2
     atlas:open-saved    {}                  Saved tab.                                    Owner: B1
     atlas:open-ask      {placeId?}          Ask tab and "Ask about this place".            Owner: B3
     atlas:region-changed {region}           the city switcher.                             Owner: B4 (emits and listens)
     atlas:theme-changed {theme}             window.atlasTheme.set().                        Anyone
   atlas.emit(name, detail) returns how many real listeners handled it (0 when no build has landed yet). The built-in
   no-op listeners make emit safe before the other builds exist; elements with data-atlas-emit and an href keep their
   normal link when nobody listens. */
(function (w, d) {
  "use strict";
  var atlas = w.atlas = w.atlas || {};
  var NAMES = ["atlas:open-report", "atlas:open-saved", "atlas:open-ask", "atlas:region-changed", "atlas:theme-changed"];
  var real = {};

  function on(name, fn) {
    real[name] = (real[name] || 0) + 1;
    var h = function (e) { fn(e.detail || {}, e); };
    d.addEventListener(name, h);
    return function off() { d.removeEventListener(name, h); real[name] = Math.max(0, (real[name] || 1) - 1); };
  }
  function emit(name, detail) {
    if (name.indexOf("atlas:") !== 0) throw new Error("atlas events start with atlas:");
    d.dispatchEvent(new CustomEvent(name, { detail: detail || {} }));
    return real[name] || 0;
  }
  NAMES.forEach(function (n) { d.addEventListener(n, function () { /* no-op fallback */ }); });
  atlas.events = NAMES.slice();
  atlas.on = on;
  atlas.emit = emit;
  atlas.listeners = function (name) { return real[name] || 0; };

  /* ---- helpers ---- */
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function icon(name, cls) {
    return '<svg class="ic' + (cls ? " " + cls : "") + '" aria-hidden="true" focusable="false"><use href="#lucide-' + esc(name) + '"/></svg>';
  }
  var ui = atlas.ui = atlas.ui || {};
  ui.esc = esc;
  ui.icon = icon;
  ui.badge = function (rating, label) {
    var m = { yes: ["yes", "Accessible"], partial: ["partial", "Partly accessible"], no: ["no", "Not accessible"], unknown: ["unknown", "Not known"] }[rating] || ["unknown", "Not known"];
    return '<span class="badge ' + m[0] + '">' + icon(m[0]) + "<span>" + esc(label || m[1]) + "</span></span>";
  };
  ui.setTab = function (name) {
    var tabs = d.querySelectorAll(".ax .tabbar .tab, .ax .nav-links [data-tab]");
    for (var i = 0; i < tabs.length; i++) {
      var t = tabs[i];
      if ((t.getAttribute("data-tab") || "") === name) t.setAttribute("aria-current", "page"); else t.removeAttribute("aria-current");
    }
  };

  /* ---- portal, toast ---- */
  var portal, toasts;
  function getPortal() {
    if (portal) return portal;
    portal = d.createElement("div");
    portal.className = "ax portal";
    toasts = d.createElement("div");
    toasts.className = "toasts";
    toasts.setAttribute("role", "status");
    toasts.setAttribute("aria-live", "polite");
    portal.appendChild(toasts);
    d.body.appendChild(portal);
    return portal;
  }
  /* ui.toast("Saved", {action: {label: "Undo", onClick: fn}, ms: 6000}) -> {close()}. Stays at least 6 s (10 s with an action). */
  ui.toast = function (message, opts) {
    opts = opts || {};
    getPortal();
    var el = d.createElement("div");
    el.className = "toast";
    var span = d.createElement("span");
    span.textContent = message;
    el.appendChild(span);
    var timer;
    function close() { clearTimeout(timer); if (el.parentNode) el.parentNode.removeChild(el); }
    if (opts.action) {
      var b = d.createElement("button");
      b.type = "button";
      b.className = "btn";
      b.textContent = opts.action.label;
      b.addEventListener("click", function () { close(); if (opts.action.onClick) opts.action.onClick(); });
      el.appendChild(b);
    }
    toasts.appendChild(el);
    timer = setTimeout(close, opts.ms || (opts.action ? 10000 : 6000));
    return { close: close };
  };

  /* ---- bottom sheet: modal, focus trap, inert background, Escape and scrim close, focus returns to the opener ---- */
  var FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]):not([type=hidden]),select:not([disabled]),textarea:not([disabled]),summary,[tabindex]:not([tabindex="-1"])';
  var sheetSeq = 0;
  /* ui.sheet.open({title, html | node, onClose, labelledBy}) -> {el, close()} */
  ui.sheet = {
    open: function (o) {
      var p = getPortal(), opener = d.activeElement, id = "atlas-sheet-" + (++sheetSeq);
      var scrim = d.createElement("div");
      scrim.className = "scrim";
      var el = d.createElement("section");
      el.className = "sheet modal";
      el.setAttribute("role", "dialog");
      el.setAttribute("aria-modal", "true");
      el.setAttribute("aria-labelledby", id + "-t");
      el.innerHTML = '<div class="grab"></div><div class="sheet-head"><h2 id="' + id + '-t" tabindex="-1">' + esc(o.title || "") +
        '</h2><button type="button" class="btn btn-icon btn-ghost" data-sheet-close aria-label="Close">' + icon("close") + "</button></div>";
      var body = d.createElement("div");
      body.className = "stack3";
      if (o.node) body.appendChild(o.node); else body.innerHTML = o.html || "";
      el.appendChild(body);
      p.insertBefore(scrim, p.firstChild);
      p.appendChild(el);
      var held = [];
      for (var i = 0; i < d.body.children.length; i++) {
        var c = d.body.children[i];
        if (c !== p && !c.inert) { c.inert = true; held.push(c); }
      }
      var closed = false;
      function close() {
        if (closed) return;
        closed = true;
        d.removeEventListener("keydown", key, true);
        held.forEach(function (c) { c.inert = false; });
        if (scrim.parentNode) scrim.parentNode.removeChild(scrim);
        if (el.parentNode) el.parentNode.removeChild(el);
        if (opener && opener.focus && d.contains(opener)) opener.focus();
        if (o.onClose) o.onClose();
      }
      function key(e) {
        if (e.key === "Escape") { e.preventDefault(); close(); return; }
        if (e.key !== "Tab") return;
        var f = [].filter.call(el.querySelectorAll(FOCUSABLE), function (n) { return n.offsetParent !== null || n === d.activeElement; });
        if (!f.length) { e.preventDefault(); return; }
        var first = f[0], last = f[f.length - 1];
        if (!el.contains(d.activeElement)) { e.preventDefault(); first.focus(); }
        else if (e.shiftKey && d.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && d.activeElement === last) { e.preventDefault(); first.focus(); }
      }
      d.addEventListener("keydown", key, true);
      scrim.addEventListener("click", close);
      el.querySelector("[data-sheet-close]").addEventListener("click", close);
      var first = el.querySelector("[data-autofocus]") || el.querySelector("h2");
      first.focus();
      return { el: el, close: close };
    }
  };

  /* ---- delegated behaviour ---- */
  d.addEventListener("click", function (e) {
    var t = e.target.closest ? e.target.closest("[data-atlas-emit],[role=switch],[role=radio],[data-atlas-theme],[data-theme-toggle]") : null;
    if (!t) return;
    if (t.hasAttribute("data-atlas-emit")) {
      var detail = {};
      if (t.getAttribute("data-place-id")) detail.placeId = t.getAttribute("data-place-id");
      if (t.getAttribute("data-region")) detail.region = t.getAttribute("data-region");
      var n = emit(t.getAttribute("data-atlas-emit"), detail);
      if (n > 0 && t.tagName === "A") e.preventDefault();   /* a listener took over; otherwise the plain href still works */
      return;
    }
    if (t.hasAttribute("data-theme-toggle")) { w.atlasTheme.set(w.atlasTheme.get() === "dark" ? "light" : "dark"); return; }
    if (t.hasAttribute("data-atlas-theme")) { w.atlasTheme.set(t.getAttribute("data-atlas-theme")); return; }
    if (t.getAttribute("role") === "switch") {
      t.setAttribute("aria-checked", t.getAttribute("aria-checked") === "true" ? "false" : "true");
      t.dispatchEvent(new CustomEvent("atlas:switch", { bubbles: true, detail: { checked: t.getAttribute("aria-checked") === "true" } }));
      return;
    }
    if (t.getAttribute("role") === "radio" && t.closest("[role=radiogroup]")) selectRadio(t);
  });
  function selectRadio(t) {
    var g = t.closest("[role=radiogroup]"), rs = g.querySelectorAll("[role=radio]");
    for (var i = 0; i < rs.length; i++) { rs[i].setAttribute("aria-checked", rs[i] === t ? "true" : "false"); rs[i].tabIndex = rs[i] === t ? 0 : -1; }
    t.focus();
    g.dispatchEvent(new CustomEvent("atlas:choice", { bubbles: true, detail: { value: t.getAttribute("data-value") } }));
  }
  d.addEventListener("keydown", function (e) {
    var t = e.target;
    if (!t.matches || !t.matches("[role=radio]") || !t.closest("[role=radiogroup]")) return;
    var map = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 };
    if (!map[e.key]) return;
    e.preventDefault();
    var rs = [].slice.call(t.closest("[role=radiogroup]").querySelectorAll("[role=radio]")), i = rs.indexOf(t);
    selectRadio(rs[(i + map[e.key] + rs.length) % rs.length]);
  });
  /* Appearance radios (name="atlas-theme") follow the theme, both ways. */
  function syncTheme() {
    var rs = d.querySelectorAll('input[name="atlas-theme"]');
    for (var i = 0; i < rs.length; i++) rs[i].checked = rs[i].value === w.atlasTheme.get();
    var dark = w.atlasTheme.get() === "dark", ts = d.querySelectorAll("[data-theme-toggle]");
    for (var j = 0; j < ts.length; j++) ts[j].setAttribute("aria-checked", dark ? "true" : "false");
  }
  d.addEventListener("change", function (e) { if (e.target.name === "atlas-theme") w.atlasTheme.set(e.target.value); });
  d.addEventListener("atlas:theme-changed", syncTheme);
  if (d.readyState === "loading") d.addEventListener("DOMContentLoaded", syncTheme); else syncTheme();
})(window, document);
