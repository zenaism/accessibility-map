/* Openway Assistant: the verifier (port of verify.py). Keeps only sentences tied to a record. */
(function (g) {
  'use strict';
  const O = (g.Openway = g.Openway || {});
  const X = g.Openway.text || require('./text.js');
  const P = g.Openway.planner || require('./planner.js');
  const { norm, tokens, stem, rhu } = X;
  const R = () => O.rules;
  const CONSTANT = ['911', '8.33', '30'];
  const nn = x => (x.includes('.') ? x : (x.replace(/^0+/, '') || '0'));
  const numbers = text => new Set((String(text).match(/\d+(?:\.\d+)?/g) || []).map(nn));

  function recordIds(results) {
    const ids = new Set();
    for (const r of results) {
      ids.add('tool:' + r.tool);
      const rows = Array.isArray(r.data) ? r.data : (r.data && typeof r.data === 'object' ? [r.data] : []);
      for (const x of rows) {
        if (x && typeof x === 'object') {
          if (x.link_id) ids.add(x.link_id);
          if (x.id) ids.add(x.id);
          for (const e of (x.events || [])) if (e.link_id) ids.add(e.link_id);
        }
      }
    }
    return ids;
  }
  const blob = results => JSON.stringify(results.map(r => r.data)).toLowerCase();
  function quotesText(results) {
    const b = blob(results), out = [];
    const re = /"(?:quote|detail|summary|notice|title|arrival|text)":"((?:[^"\\]|\\.)*)"/g;
    let m;
    while ((m = re.exec(b)) !== null) out.push(norm(m[1]));
    return out.join(' ');
  }
  function derivedFromResults(results) {
    const out = new Set();
    const walk = x => {
      if (Array.isArray(x)) { for (const v of x) walk(v); return; }
      if (x && typeof x === 'object') {
        for (const k of Object.keys(x)) {
          const v = x[k];
          if (k === 'miles' && typeof v === 'number') { out.add(String(Math.max(50, rhu(v * 5280 / 50) * 50))); out.add((rhu(v * 10) / 10).toFixed(1)); }
          if (k === 'share_steeper_than_ramp' && typeof v === 'number') out.add(String(rhu(v * 100)));
          walk(v);
        }
      }
    };
    walk(results.map(r => r.data));
    let n = 0;
    for (const r of results) if (Array.isArray(r.data)) n += r.data.length;
    out.add(String(n));
    return out;
  }
  function allowedNumbers(results, plan, question, derived, asOf) {
    const base = new Set([...numbers(blob(results)), ...numbers(question), ...CONSTANT, ...derived.map(nn)]);
    for (const d of derivedFromResults(results)) base.add(nn(d));
    if (plan && plan.when) for (const x of numbers(plan.when.start + ' ' + plan.when.end)) base.add(x);
    if (asOf) for (const x of numbers(asOf)) base.add(x);
    for (const x of Array.from(base)) if (/^\d+$/.test(x) && +x >= 13 && +x <= 23) base.add(String(+x - 12));
    return base;
  }
  function subtokens(text) {
    const out = new Set();
    for (const w of tokens(text)) { out.add(stem(w)); for (const x of w.split(/[-']/)) if (x) out.add(stem(x)); }
    return out;
  }
  function knownNames(results, question, planText) {
    const r = R();
    const out = new Set([...subtokens(blob(results)), ...subtokens(question), ...subtokens(planText)]);
    for (const w of tokens(r.MONTHS_DAYS.concat(r.KNOWN_CAPS, r.REGION_KEYS).join(' '))) out.add(stem(w));
    for (const [, label] of r.SOURCE_KINDS) for (const w of tokens(label)) out.add(stem(w));
    for (const w of tokens(Object.values(r.NEED_LABELS).join(' ') + ' ' + Object.values(r.TYPE_LABELS).join(' '))) out.add(stem(w));
    return out;
  }
  function checkSentence(s, ids, nums, names, quotes) {
    const r = R();
    for (const ref of s.refs) if (!ids.has(ref)) return 'unknown_record';
    if (s.kind === 'claim' && !s.refs.length) return 'no_citation';
    const t = norm(s.text);
    if (s.kind !== 'disclaimer') for (const b of r.BANNED) if ((' ' + t + ' ').includes(' ' + norm(b) + ' ')) return 'banned_phrase';
    for (const b of r.BANNED_WORDS) if ((' ' + t + ' ').includes(' ' + b + ' ')) return 'banned_phrase';
    if (s.kind === 'meta' || s.kind === 'disclaimer') return null;
    for (const x of numbers(s.text)) if (!nums.has(x)) return 'number_not_in_results';
    const qre = /["“]([^"”]{3,})["”]/g;
    let m;
    while ((m = qre.exec(s.text)) !== null) if (!quotes.includes(norm(m[1]))) return 'quote_not_in_record';
    for (const w of P.capitalized(s.text, '.?!:;(')) {
      const k = stem(norm(w));
      if (k && !names.has(k) && k.length > 1) return 'name_not_in_results';
    }
    return null;
  }
  function verify(a, results, plan, ctx, question) {
    const ids = recordIds(results);
    const derived = [];
    for (const s of a.headline.concat(a.details)) for (const d of s.derived) derived.push(d);
    const nums = allowedNumbers(results, plan, question || '', derived, a.as_of);
    const names = knownNames(results, question || '', plan ? JSON.stringify(plan) : '');
    const quotes = quotesText(results);
    const issues = [];
    for (const section of ['headline', 'details']) {
      const keep = [];
      a[section].forEach((s, i) => {
        const bad = checkSentence(s, ids, nums, names, quotes);
        if (bad) issues.push({ section, index: i, rule: bad, text: s.text }); else keep.push(s);
      });
      a[section] = keep;
    }
    a.cards.forEach((c, i) => { if (!ids.has(c.place_id)) issues.push({ section: 'card', index: i, rule: 'unknown_record', text: c.name }); });
    a.cards = a.cards.filter(c => ids.has(c.place_id));
    a.removed = issues.length;
    if (!a.headline.length && a.kind !== 'emergency') {
      a.kind = 'unknown';
      a.headline = [{ text: "I'm not sure I can answer that reliably, so I'd rather say I don't know.", refs: [], kind: 'meta', derived: [] },
        { text: 'Please call the place or check its own website.', refs: [], kind: 'meta', derived: [] }];
      a.cards = []; a.details = [];
    }
    a.verified = issues.length === 0;
    return [a, issues];
  }
  const V = { verify, checkSentence, numbers };
  O.verify = V;
  if (typeof module !== 'undefined') module.exports = V;
})(typeof globalThis !== 'undefined' ? globalThis : this);
