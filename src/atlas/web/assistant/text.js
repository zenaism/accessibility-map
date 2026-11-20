/* Openway Assistant: text helpers shared by the planner, composer and verifier (port of planner.py / composer.py helpers).
   Plain script, no build step. In the browser it attaches to window.Openway; in Node (tests) it also exports. */
(function (g) {
  'use strict';
  const O = (g.Openway = g.Openway || {});
  O.rules = O.rules || null;
  O.setRules = function (r) { O.rules = r; O._normCache = new Map(); };
  O._normCache = new Map();

  const TOKEN = /[a-z0-9]+(?:['-][a-z0-9]+)*/g;
  function norm(s) {
    s = String(s == null ? '' : s).toLowerCase().replace(/’/g, "'").replace(/mt\./g, 'mt').replace(/st\./g, 'st');
    return (s.match(TOKEN) || []).join(' ');
  }
  function tokens(s) { const n = norm(s); return n ? n.split(' ') : []; }
  function nphrase(p) {
    let v = O._normCache.get(p);
    if (v === undefined) { v = norm(p); O._normCache.set(p, v); }
    return v;
  }
  function has(t, phrase) { return (' ' + t + ' ').includes(' ' + nphrase(phrase) + ' '); }
  function hasAny(t, phrases) { for (const p of phrases) if (has(t, p)) return p; return null; }
  function stem(w) {
    w = w.replace(/'s$/, '');
    return w.length > 3 && w.endsWith('s') && !w.endsWith('ss') ? w.slice(0, -1) : w;
  }
  function lev(a, b) {
    let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
    for (let i = 1; i <= a.length; i++) {
      const cur = [i];
      for (let j = 1; j <= b.length; j++) {
        cur.push(Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] !== b[j - 1] ? 1 : 0)));
      }
      prev = cur;
    }
    return prev[prev.length - 1];
  }
  function tokMatch(q, n) {
    if (q === n) return true;
    const m = Math.min(q.length, n.length);
    if (m < 7) return false;
    return lev(q, n) <= (m >= 10 ? 2 : 1);
  }
  const rhu = x => Math.floor(x + 0.5);
  const isDigits = s => /^[0-9]+$/.test(s);
  const unique = a => Array.from(new Set(a));
  function cmp(a, b) { return a < b ? -1 : a > b ? 1 : 0; }
  function cmpKeys(ka, kb) {
    for (let i = 0; i < ka.length; i++) { const c = cmp(ka[i], kb[i]); if (c) return c; }
    return 0;
  }
  const T = { norm, tokens, has, hasAny, stem, lev, tokMatch, rhu, isDigits, unique, cmp, cmpKeys };
  O.text = T;
  if (typeof module !== 'undefined') module.exports = T;
})(typeof globalThis !== 'undefined' ? globalThis : this);
