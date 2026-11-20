/* Openway Assistant: engines behind one interface (see assistant_build_spec.md section 4).
   GuidedEngine: the whole pipeline in the browser (rules + templates, no model, nothing sent anywhere).
   LocalEngine : talks to the localhost server (model planner/composer through Ollama), with fallback.
   ask(message, context) -> async iterator of events: clarify, text, detail, card, action, unknown, sources, meta, done, error. */
(function (g) {
  'use strict';
  const O = (g.Openway = g.Openway || {});
  const need = n => g.Openway[n] || require('./' + n + '.js');
  const tools = need('tools'), P = need('planner'), C = need('composer'), V = need('verify');

  function toEvents(a) {
    const ev = [];
    if (a.clarify) ev.push(Object.assign({ type: 'clarify' }, a.clarify));
    ev.push({ type: 'text', kind: a.kind, delta: a.headline.map(s => s.text).join(' '), parts: a.headline.map(s => s.text) });
    if (a.details.length) ev.push({ type: 'detail', items: a.details.map(s => s.text) });
    for (const c of a.cards) ev.push({ type: 'card', card: c });
    for (const x of a.actions) { const o = { type: 'action', action: x.type }; for (const k of Object.keys(x)) if (k !== 'type') o[k] = x[k]; ev.push(o); }
    if (a.call) ev.push(Object.assign({ type: 'call' }, a.call));
    if (a.unknown.length || ['unknown', 'no_data', 'out_of_area'].includes(a.kind)) ev.push({ type: 'unknown', about: a.unknown.slice(), call: a.call });
    if (a.sources.length) ev.push({ type: 'sources', items: a.sources });
    ev.push({ type: 'meta', as_of: a.as_of, notes: a.notes, plan: a.plan, engine: a.engine });
    ev.push({ type: 'done', verified: a.verified, removed: a.removed });
    return ev;
  }

  function GuidedEngine(regionFiles, rules) {
    O.setRules(rules);
    this.kb = tools.buildKB(regionFiles);
    this.be = tools.Backend(this.kb, rules);
    this.index = new P.Index(this.be.places());
    this.name = 'guided';
  }
  GuidedEngine.prototype.answer = function (text, ctx) {
    ctx = Object.assign({ today: new Date().toISOString().slice(0, 10), region: null, location: null, needs: {}, plain: false }, ctx || {});
    const pl = P.plan(text, ctx, this.index);
    const results = tools.execute(pl, ctx, this.be);
    const asOf = this.be.as_of();
    let a = C.compose(pl, results, ctx, asOf);
    const [v, issues] = V.verify(a, results, pl, ctx, text);
    v.engine = 'rules';
    this.last = { issues, results, plan: pl };
    return v;
  };
  GuidedEngine.prototype.ask = async function* (text, ctx) {
    try { for (const e of toEvents(this.answer(text, ctx))) yield e; }
    catch (err) { yield { type: 'error', message: 'Something went wrong while looking that up. Please try again or use a button.' }; }
  };
  GuidedEngine.prototype.info = async function () { return { engine: 'guided', model: false, as_of: this.be.as_of() }; };

  /** Talks to the local server: POST /ask (server-sent events). Falls back to the guided engine when the server or model is unavailable. */
  function LocalEngine(baseUrl, fallback) { this.base = baseUrl || ''; this.fallback = fallback || null; this.name = 'local'; }
  LocalEngine.prototype.info = async function () {
    try { const r = await fetch(this.base + '/api/health', { cache: 'no-store' }); return Object.assign({ engine: 'local' }, await r.json()); }
    catch (e) { return { engine: 'local', model: false, error: 'server not reachable' }; }
  };
  LocalEngine.prototype.ask = async function* (text, ctx, opts) {
    opts = opts || {};
    let res;
    try {
      res = await fetch(this.base + '/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: text, context: ctx, image: opts.image || null, mode: opts.mode || 'model' }), signal: opts.signal });
      if (!res.ok || !res.body) throw new Error('bad response');
    } catch (err) {
      if (err && err.name === 'AbortError') return;
      yield { type: 'note', message: 'The local model is not reachable, so I used guided mode instead.' };
      if (this.fallback) { for await (const e of this.fallback.ask(text, ctx)) yield e; } else yield { type: 'error', message: 'I could not reach the local server. Start it with scripts/serve_assistant.sh, or switch to Guided mode.' };
      return;
    }
    const reader = res.body.getReader(), dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf('\n\n')) >= 0) {
        const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
        const line = chunk.split('\n').find(l => l.startsWith('data:'));
        if (line) { try { yield JSON.parse(line.slice(5).trim()); } catch (e) { /* ignore a broken chunk */ } }
      }
    }
  };
  const E = { GuidedEngine, LocalEngine, toEvents };
  O.engine = E;
  if (typeof module !== 'undefined') module.exports = E;
})(typeof globalThis !== 'undefined' ? globalThis : this);
