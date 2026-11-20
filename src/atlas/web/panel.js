/* The Directions panel of the Accessibility Map (inlined into the map page by src/atlas/routing_ui.py).
 *
 * Part 1: RouteUtil, pure helpers (time, links, text), tested in Node (tests/js/panel.test.js).
 * Part 2: initRoutingPanel(ctx), the interface. ctx brings the map page's own objects (map, L, ITEMS, ...).
 *
 * Reading order of the panel is the order of its parts: title, From, To, route type, status, result
 * (summary, steps, actions). The search runs in a Web Worker built from ROUTING_CORE_SRC, the text of
 * routing.js + directions.js, which the page defines before this file.
 */
const RouteUtil = (function () {
  'use strict';
  const PACE_MPH = 2.5; // stated on screen; a guess until we have a source or ask users
  const FT_PER_MIN = (PACE_MPH * 5280) / 60;

  function minutes(feet) {
    return feet / FT_PER_MIN;
  }
  function timeText(feet) {
    const m = minutes(feet);
    if (m < 0.5) return 'under 1 minute';
    const r = Math.max(1, Math.round(m));
    if (r < 60) return r === 1 ? '1 minute' : `${r} minutes`;
    const h = Math.floor(r / 60);
    const mm = r % 60;
    return `${h} hour${h > 1 ? 's' : ''}` + (mm ? ` ${mm} minutes` : '');
  }
  function distText(feet) {
    const miles = feet / 5280;
    return `${miles < 0.1 ? '0.1' : miles.toFixed(1)} miles (${feet.toLocaleString('en-US')} feet)`;
  }
  /** One place or point as a link token: a place's link_id, "here", or "@lat;lon". */
  function token(sel) {
    if (!sel) return '';
    if (sel.kind === 'place') return sel.it.p.link_id;
    if (sel.kind === 'here') return 'here';
    return `@${sel.pt[0].toFixed(5)};${sel.pt[1].toFixed(5)}`;
  }
  function formatHash(fromTok, toTok, profile) {
    return `#route=${encodeURIComponent(fromTok)},${encodeURIComponent(toTok)}&profile=${profile}`;
  }
  /** Parse "#route=from,to&profile=blind". Returns null when the hash is not a route link. */
  function parseHash(hash) {
    const m = /^#route=([^,&]*),([^&]*)(?:&profile=(\w+))?$/.exec(hash || '');
    if (!m) return null;
    const dec = (s) => {
      try {
        return decodeURIComponent(s);
      } catch (e) {
        return '';
      }
    };
    return {
      from: dec(m[1]),
      to: dec(m[2]),
      profile: m[3] === 'blind' ? 'blind' : 'wheelchair',
    };
  }
  /** "@39.5,-84.7" tokens back to [lat, lon] (or null). */
  function parsePoint(tok) {
    const m = /^@(-?\d+(?:\.\d+)?);(-?\d+(?:\.\d+)?)$/.exec(tok || '');
    return m ? [parseFloat(m[1]), parseFloat(m[2])] : null;
  }
  function googleUrl(fromPt, toPt) {
    const p = (x) => `${x[0].toFixed(6)},${x[1].toFixed(6)}`;
    return (
      'https://www.google.com/maps/dir/?api=1&travelmode=walking' +
      (fromPt ? `&origin=${p(fromPt)}` : '') +
      `&destination=${p(toPt)}`
    );
  }
  const PROFILE_LABEL = { wheelchair: 'Wheelchair', blind: 'Blind or low vision' };
  /** The route as plain text for Copy directions. */
  function routeText(m) {
    const r = m.result;
    const lines = [
      `Directions from ${m.fromName} to ${m.toName} (${PROFILE_LABEL[r.profile]} route)`,
      `About ${timeText(r.length_feet)}, ${distText(r.length_feet)}. Time is an estimate at ${PACE_MPH} mph.`,
      'No stairs.',
      r.crossings_text,
      r.compared_with_shortest,
      '',
      ...r.directions.map((d, i) => `${i + 1}. ${d}`),
      `${r.directions.length + 1}. Arrive at ${m.toName}.`,
    ];
    if (m.doorNote) lines.push(m.doorNote);
    lines.push('', 'Suggested from map data, not checked on site.');
    if (m.link) lines.push(m.link);
    return lines.join('\n');
  }
  /** Words ranked: starts with the text, a word starts with it, contains it. Empty text matches nothing. */
  function rankPlaces(names, query, limit) {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    const out = [];
    names.forEach((n, i) => {
      const s = n.toLowerCase();
      let score = -1;
      if (s.startsWith(q)) score = 0;
      else if (s.split(/[^a-z0-9']+/).some((w) => w.startsWith(q))) score = 1;
      else if (s.includes(q)) score = 2;
      else if (q.split(/\s+/).every((t) => s.includes(t))) score = 3;
      if (score >= 0) out.push([score, s.length, i]);
    });
    out.sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2]);
    return out.slice(0, limit || 8).map((x) => x[2]);
  }
  return {
    PACE_MPH,
    minutes,
    timeText,
    distText,
    token,
    formatHash,
    parseHash,
    parsePoint,
    googleUrl,
    routeText,
    rankPlaces,
    PROFILE_LABEL,
  };
})();
if (typeof module === 'object' && module.exports) module.exports = { RouteUtil };

// ============================================================================================
function initRoutingPanel(ctx) {
  'use strict';
  const { map, L, ITEMS, PHONE, esc, store, VIEW, ICONS, CFG } = ctx;
  const U = RouteUtil;
  const NOT_CHECKED = 'Suggested from map data, not checked on site.';
  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)');
  const enabledRegions = new Set(CFG.regions);
  const $ = (sel, root) => (root || document).querySelector(sel);

  // ---------------------------------------------------------------- icons (20 x 20, stroke only)
  const ICON = {
    straight: '<path d="M10 17V4M5 9l5-5 5 5"/>',
    right: '<path d="M5 17V9h9M10 4l5 5-5 5"/>',
    left: '<path d="M15 17V9H6M10 4 5 9l5 5"/>',
    'bear-right': '<path d="M5 15 14 6M8 6h6v6"/>',
    'bear-left': '<path d="M15 15 6 6M12 6H6v6"/>',
    'turn-around': '<path d="M6 17V8a4 4 0 0 1 8 0v3M11 9l3 3 3-3"/>',
    'turn-right': '<path d="M5 17V9h9M10 4l5 5-5 5"/>',
    'turn-left': '<path d="M15 17V9H6M10 4 5 9l5 5"/>',
    start: '<path d="M10 17V4M5 9l5-5 5 5"/>',
    cross: '<path d="M4 4v12M8 4v12M12 4v12M16 4v12" stroke-width="2.6"/>',
    flag: '<path d="M5 17V3m0 0h10l-2 3.5L15 10H5"/>',
    warn: '<path d="M10 3 18 17H2zM10 8v4M10 14.2v.1"/>',
    check: '<path d="m4 10.5 4 4 8-9"/>',
    swap: '<path d="M6 16V4M2.5 7.5 6 4l3.5 3.5M14 4v12M10.5 12.5 14 16l3.5-3.5"/>',
    pin: '<circle cx="10" cy="10" r="3.2" fill="currentColor"/><circle cx="10" cy="10" r="7"/>',
    map: '<path d="M10 17s-5-4.6-5-8.5a5 5 0 0 1 10 0C15 12.4 10 17 10 17z"/><circle cx="10" cy="8.5" r="1.8"/>',
    copy: '<rect x="7" y="7" width="9" height="10" rx="1.5"/><path d="M13 7V4.5A1.5 1.5 0 0 0 11.5 3h-7A1.5 1.5 0 0 0 3 4.5v7A1.5 1.5 0 0 0 4.5 13H7"/>',
    link: '<path d="M8.5 11.5a3 3 0 0 0 4.2 0l3-3a3 3 0 0 0-4.2-4.2l-1 1M11.5 8.5a3 3 0 0 0-4.2 0l-3 3a3 3 0 0 0 4.2 4.2l1-1"/>',
    google: '<path d="M10 17s-5-4.6-5-8.5a5 5 0 0 1 10 0C15 12.4 10 17 10 17z"/><path d="M13 3l4 0 0 4M17 3l-5 5"/>',
    close: '<path d="m5 5 10 10M15 5 5 15"/>',
    back: '<path d="M12.5 4.5 7 10l5.5 5.5"/>',
    up: '<path d="m5 12 5-5 5 5"/>',
    down: '<path d="m5 8 5 5 5-5"/>',
    prev: '<path d="m5 12 5-5 5 5"/>',
    next: '<path d="m5 8 5 5 5-5"/>',
    locate: '<circle cx="10" cy="10" r="3" fill="currentColor"/><circle cx="10" cy="10" r="7"/>',
    stairs: '<path d="M3 16h4v-4h4V8h4V4h2"/>',
  };
  const svg = (name, cls) =>
    `<svg class="i ${cls || ''}" viewBox="0 0 20 20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICON[name]}</svg>`;

  // ---------------------------------------------------------------- state
  const S = {
    open: false,
    from: null, // {kind:'place'|'here'|'map', it?, pt:[lat,lon], door?, note?}
    to: null,
    profile: store.get('atlas-route-profile') === 'blind' ? 'blind' : 'wheelchair',
    result: null,
    model: null,
    token: 0, // newest request wins
    state: 'empty',
    step: -1,
    height: 'steps', // phone sheet height: summary | steps | full
    opener: null,
    picking: null,
    wantHere: false,
  };
  const stats = { loadMs: null, buildMs: null, searchMs: null, nodes: 0, edges: 0, fromCache: false };

  // ---------------------------------------------------------------- places
  const regionOfPoint = (pt) => {
    let best = null;
    let bd = Infinity;
    for (const r of Object.keys(VIEW)) {
      const c = VIEW[r][0];
      const d = Math.hypot((c[0] - pt[0]) * 111, (c[1] - pt[1]) * 85);
      if (d < bd) [best, bd] = [r, d];
    }
    return bd < 40 ? best : null;
  };
  const regionOf = (sel) => (sel.kind === 'place' ? sel.it.p.region : regionOfPoint(sel.pt));
  const lastDirection = (it) => {
    const r = it.p.getting_there && it.p.getting_there.route;
    return r && r.directions.length ? r.directions[r.directions.length - 1] : '';
  };
  /** Where a route to this place should end: its accessible entrance when the saved route knows one. */
  function placeSel(it) {
    const r = it.p.getting_there && it.p.getting_there.route;
    const noDoor = /no accessible door is mapped/.test(lastDirection(it));
    if (r && r.line && r.line.length && !noDoor) {
      const e = r.line[r.line.length - 1];
      return { kind: 'place', it, pt: [e[1], e[0]], door: true };
    }
    return { kind: 'place', it, pt: it.pts[0], door: false, noDoorKnown: !!(r && noDoor) };
  }
  const nameOf = (sel) =>
    !sel ? '' : sel.kind === 'place' ? sel.it.p.name : sel.kind === 'here' ? 'My location' : 'The point you picked on the map';
  const routable = (it) => enabledRegions.has(it.p.region) && it.p.layer !== 'event';
  const searchable = ITEMS.filter(routable);
  const searchNames = searchable.map((it) => it.p.name);
  ctx.decorateCard = ctx.decorateDetails = ctx.decoratePopup = () => {};
  if (!searchable.length) return ctx; // this page has no region with a walking graph: no panel, old links stay

  // ---------------------------------------------------------------- the search backend (worker or inline)
  const backends = {};
  function backendFor(region) {
    if (backends[region]) return backends[region];
    const url = new URL(`${CFG.base}${region}.graph.json`, location.href).href;
    const b = { region, url, state: 'idle', promise: null, nextId: 1, waiting: new Map(), worker: null, G: null };
    const GLUE = `
let G = null;
self.onmessage = async (e) => {
  const m = e.data;
  try {
    if (m.type === 'load') {
      const t0 = performance.now();
      const res = await fetch(m.url);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const json = await res.json();
      const t1 = performance.now();
      G = AtlasRoutingCore.loadGraph(json);
      self.postMessage({type: 'ready', id: m.id, fetchParse: t1 - t0, build: performance.now() - t1, nodes: G.n, edges: G.m});
    } else if (m.type === 'route') {
      const t0 = performance.now();
      const r = AtlasDirections.route(G, ...m.args);
      self.postMessage({type: 'result', id: m.id, result: r, ms: performance.now() - t0});
    }
  } catch (err) {
    self.postMessage({type: 'error', id: m.id, message: String((err && err.message) || err)});
  }
};`;
    const ask = (msg) =>
      new Promise((resolve, reject) => {
        const id = b.nextId++;
        b.waiting.set(id, { resolve, reject });
        if (b.worker) b.worker.postMessage({ ...msg, id });
        else inline(msg).then((v) => resolve(v), reject);
      });
    function onMessage(e) {
      const m = e.data;
      const w = b.waiting.get(m.id);
      if (!w) return;
      b.waiting.delete(m.id);
      if (m.type === 'error') w.reject(new Error(m.message));
      else w.resolve(m);
    }
    async function inline(msg) {
      // no Worker available (or it failed to start): same code on the page's main thread
      if (!window.AtlasRoutingCore) new Function(ROUTING_CORE_SRC)();
      if (msg.type === 'load') {
        const t0 = performance.now();
        const json = await (await fetch(msg.url)).json();
        const t1 = performance.now();
        b.G = window.AtlasRoutingCore.loadGraph(json);
        return { type: 'ready', fetchParse: t1 - t0, build: performance.now() - t1, nodes: b.G.n, edges: b.G.m };
      }
      const t0 = performance.now();
      const r = window.AtlasDirections.route(b.G, ...msg.args);
      return { type: 'result', result: r, ms: performance.now() - t0 };
    }
    b.start = () => {
      if (b.promise) return b.promise;
      b.state = 'loading';
      try {
        const blob = new Blob([ROUTING_CORE_SRC + '\n' + GLUE], { type: 'text/javascript' });
        b.worker = new Worker(URL.createObjectURL(blob));
        b.worker.onmessage = onMessage;
        b.worker.onerror = () => {
          // the worker could not start: fall back to the main thread, once
          if (b.state !== 'loading') return;
          b.worker = null;
          b.promise = null;
          b.waiting.forEach((w) => w.reject(new Error('worker failed')));
          b.waiting.clear();
          b.start();
        };
      } catch (e) {
        b.worker = null;
      }
      b.promise = ask({ type: 'load', url })
        .then((m) => {
          b.state = 'ready';
          Object.assign(stats, { loadMs: m.fetchParse, buildMs: m.build, nodes: m.nodes, edges: m.edges });
          return b;
        })
        .catch((err) => {
          b.state = 'error';
          b.promise = null;
          b.error = err;
          throw err;
        });
      return b.promise;
    };
    b.route = (args) =>
      ask({ type: 'route', args }).then((m) => {
        stats.searchMs = m.ms;
        return m.result;
      });
    backends[region] = b;
    return b;
  }

  // ---------------------------------------------------------------- DOM
  const root = document.createElement('section');
  root.id = 'dirp';
  root.className = 'dirp';
  root.hidden = true;
  root.setAttribute('aria-labelledby', 'dp-title');
  root.dataset.state = 'empty';
  root.dataset.height = 'steps';
  root.innerHTML = `
  <div class="dp-top">
    <button type="button" class="ghost dp-back" id="dp-back">${svg('back')}<span class="dp-back-d">Back to places</span><span class="dp-back-p">Close</span></button>
    <h2 id="dp-title" tabindex="-1">Directions</h2>
  </div>
  <div class="dp-scroll" id="dp-scroll">
  <div class="dp-form" id="dp-form">
    <div class="dp-fields">
      ${fieldHtml('from', 'From', 'Start')}
      <button type="button" class="dp-swap" id="dp-swap" aria-label="Swap start and destination">${svg('swap')}</button>
      ${fieldHtml('to', 'To', 'Destination')}
    </div>
    <fieldset class="dp-profile">
      <legend>Route type</legend>
      <label class="dp-radio"><input type="radio" name="dp-profile" value="wheelchair"><span>Wheelchair</span></label>
      <label class="dp-radio"><input type="radio" name="dp-profile" value="blind"><span>Blind or low vision</span></label>
      <p class="dp-help" id="dp-profile-help"></p>
    </fieldset>
  </div>
  <div class="dp-msgs">
    <p class="dp-msg" id="dp-status" role="status" aria-live="polite"></p>
    <div class="dp-msg dp-alert" id="dp-alert" role="alert" hidden></div>
    <div class="dp-ask" id="dp-ask" hidden>
      <p>To start from where you are, your browser will ask to share your location. It is used only on this device to find your start, and is never sent to us.</p>
      <div class="dp-btns"><button type="button" class="primary" id="dp-ask-yes">Continue</button><button type="button" id="dp-ask-no">Not now</button></div>
    </div>
    <div class="dp-pick" id="dp-pick" hidden>
      <p id="dp-pick-text"></p>
      <button type="button" id="dp-pick-cancel">Cancel</button>
    </div>
    <p class="dp-help" id="dp-empty">Choose where you are starting and where you are going.</p>
  </div>
  <section class="dp-result" id="dp-result" aria-labelledby="dp-sum-h" hidden>
    <h3 id="dp-sum-h" tabindex="-1"></h3>
    <p class="dp-ft" id="dp-fromto"></p>
    <ul class="dp-facts" id="dp-facts"></ul>
    <p class="dp-compare" id="dp-compare"></p>
    <p class="dp-note" id="dp-note"></p>
    <div class="dp-sheetbtns" id="dp-sheetbtns">
      <button type="button" class="primary" id="dp-toggle-steps" aria-expanded="true">${svg('up')}<span>Steps</span></button>
      <button type="button" id="dp-change">Change</button>
      <button type="button" id="dp-expand" aria-pressed="false">Full list</button>
    </div>
    <div class="dp-stepsbox" id="dp-stepsbox">
      <div class="dp-stepnav">
        <p id="dp-stepof" class="dp-stepof">Steps</p>
        <div class="dp-btns"><button type="button" id="dp-prev" aria-label="Previous step">${svg('prev')}<span>Previous</span></button><button type="button" id="dp-next" aria-label="Next step">${svg('next')}<span>Next</span></button></div>
      </div>
      <ol class="dp-steps" id="dp-steps" role="list"></ol>
      <p class="dp-doornote" id="dp-doornote" hidden></p>
      <div class="dp-actions" id="dp-actions">
        <button type="button" id="dp-copy-text">${svg('copy')}Copy directions</button>
        <button type="button" id="dp-copy-link">${svg('link')}Copy link</button>
        <a class="btn" id="dp-google" target="_blank" rel="noopener">${svg('google')}Open in Google Maps<span class="vh"> (opens in a new tab)</span></a>
        <span id="dp-report-slot"></span>
      </div>
    </div>
  </section>
  </div>
  <p class="vh" id="dp-live" role="status" aria-live="polite"></p>`;
  function fieldHtml(id, label, what) {
    return `<div class="dp-field" data-field="${id}">
      <label for="dp-${id}">${label}</label>
      <div class="dp-combo">
        <input id="dp-${id}" type="text" role="combobox" aria-expanded="false" aria-controls="dp-${id}-list" aria-autocomplete="list"
          autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="${id === 'from' ? 'Place name, or My location' : 'Place name'}" aria-describedby="dp-${id}-sel">
        <button type="button" class="dp-clear" data-clear="${id}" aria-label="Clear ${label}" hidden>${svg('close')}</button>
        <ul id="dp-${id}-list" class="dp-list" role="listbox" aria-label="${what} suggestions" hidden></ul>
      </div>
      <p class="vh" id="dp-${id}-sel"></p>
    </div>`;
  }
  const appEl = $('.app') || document.body;
  appEl.append(root);
  const el = (id) => root.querySelector('#' + id);
  const fieldEls = { from: el('dp-from'), to: el('dp-to') };

  // ---------------------------------------------------------------- announcements and messages
  let liveTimer = null;
  function announce(text) {
    const live = el('dp-live');
    live.textContent = '';
    clearTimeout(liveTimer);
    liveTimer = setTimeout(() => (live.textContent = text), 60);
  }
  function setState(state) {
    S.state = state;
    root.dataset.state = state;
    root.classList.toggle('has-route', state === 'route');
    document.body.classList.toggle('dp-has-route', state === 'route');
  }
  function clearMsgs() {
    el('dp-status').textContent = '';
    el('dp-alert').hidden = true;
    el('dp-alert').innerHTML = '';
    el('dp-ask').hidden = true;
    el('dp-pick').hidden = true;
    el('dp-empty').hidden = true;
  }
  function status(state, text) {
    clearMsgs();
    setState(state);
    el('dp-status').textContent = text;
    root.classList.remove('is-error');
  }
  /** An error in words: what happened and what to do next; extra = buttons (HTML). */
  function problem(state, text, extra) {
    clearMsgs();
    setState(state);
    hideResult();
    const a = el('dp-alert');
    a.hidden = false;
    a.innerHTML = `<p>${esc(text)}</p>${extra || ''}`;
    root.classList.add('is-error');
    announce(text);
  }
  function hideResult() {
    el('dp-result').hidden = true;
    clearRoute();
    S.result = null;
  }
  const googleLinkHtml = () => {
    const toPt = S.to && S.to.pt;
    if (!toPt) return '';
    const href = U.googleUrl(S.from && S.from.pt, toPt);
    return `<a class="btn" target="_blank" rel="noopener" href="${esc(href)}">Open in Google Maps<span class="vh"> (opens in a new tab)</span></a>`;
  };

  // ---------------------------------------------------------------- comboboxes
  const combos = {};
  function makeCombo(id) {
    const input = fieldEls[id];
    const list = el(`dp-${id}-list`);
    const clear = root.querySelector(`[data-clear=${id}]`);
    const selNote = el(`dp-${id}-sel`);
    let options = [];
    let active = -1;
    const c = { id, input, list };
    function specials() {
      const out = [];
      if (id === 'from') out.push({ type: 'here', label: 'My location', sub: 'Asks your browser for permission', icon: 'locate' });
      out.push({ type: 'map', label: 'Pick on map', sub: 'Then tap the map', icon: 'map' });
      return out;
    }
    function build() {
      const q = input.value;
      const hit = U.rankPlaces(searchNames, q, 8).map((i) => {
        const it = searchable[i];
        return { type: 'place', it, label: it.p.name, sub: `${ICONS[it.p.layer][0]} · ${ctx.RATINGS[it.p.access_rating][0]}`, icon: 'pin' };
      });
      options = [...hit, ...specials()];
      list.innerHTML = options
        .map(
          (o, i) =>
            `<li role="option" id="dp-${id}-o${i}" data-i="${i}" aria-selected="false" class="dp-opt${o.type === 'place' ? '' : ' special'}">${svg(o.icon)}<span class="dp-opt-t"><b>${esc(o.label)}</b><small>${esc(o.sub)}</small></span></li>`
        )
        .join('');
      if (q.trim() && !hit.length) {
        list.insertAdjacentHTML('afterbegin', `<li class="dp-none" role="presentation">No place called “${esc(q.trim())}” on this map.</li>`);
      }
      active = -1;
      input.removeAttribute('aria-activedescendant');
    }
    function open() {
      build();
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
    }
    function close() {
      list.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
      active = -1;
    }
    function highlight(i) {
      list.querySelectorAll('[role=option]').forEach((o, k) => o.setAttribute('aria-selected', k === i ? 'true' : 'false'));
      active = i;
      if (i >= 0) {
        input.setAttribute('aria-activedescendant', `dp-${id}-o${i}`);
        const o = list.querySelector(`#dp-${id}-o${i}`);
        if (o && o.scrollIntoView) o.scrollIntoView({ block: 'nearest' });
      } else input.removeAttribute('aria-activedescendant');
    }
    function choose(i) {
      const o = options[i];
      if (!o) return;
      close();
      if (o.type === 'place') setSelection(id, placeSel(o.it), { focusNext: true });
      else if (o.type === 'here') requestHere(id);
      else startPick(id);
    }
    c.setText = (sel) => {
      input.value = sel ? nameOf(sel) : '';
      clear.hidden = !input.value;
      selNote.textContent = sel ? `Selected: ${nameOf(sel)}` : '';
    };
    c.close = close;
    c.isOpen = () => !list.hidden;
    input.addEventListener('input', () => {
      if (S[id]) {
        S[id] = null; // typing again drops the old choice
        selNote.textContent = '';
        onSelectionsChanged();
      }
      clear.hidden = !input.value;
      open();
    });
    input.addEventListener('click', () => {
      if (list.hidden && !S[id]) open();
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (list.hidden) open();
        highlight(Math.min(options.length - 1, active + 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (list.hidden) open();
        highlight(Math.max(0, active - 1));
      } else if (e.key === 'Enter') {
        if (!list.hidden) {
          e.preventDefault();
          choose(active >= 0 ? active : input.value.trim() ? 0 : -1);
        }
      } else if (e.key === 'Escape' && !list.hidden) {
        e.preventDefault();
        e.stopPropagation();
        close();
      }
    });
    list.addEventListener('mousedown', (e) => e.preventDefault()); // keep focus in the input
    list.addEventListener('click', (e) => {
      const o = e.target.closest('[role=option]');
      if (o) choose(+o.dataset.i);
    });
    input.addEventListener('blur', () =>
      setTimeout(() => {
        if (document.activeElement !== input) close();
      }, 120)
    );
    clear.addEventListener('click', () => {
      S[id] = null;
      c.setText(null);
      onSelectionsChanged();
      input.focus();
    });
    combos[id] = c;
    return c;
  }
  makeCombo('from');
  makeCombo('to');

  function setSelection(id, sel, opts) {
    S[id] = sel;
    combos[id].setText(sel);
    combos[id].close();
    onSelectionsChanged(opts);
    if (opts && opts.focusNext && !S.result) {
      const other = id === 'from' ? 'to' : 'from';
      if (!S[other]) fieldEls[other].focus();
    }
  }

  // ---------------------------------------------------------------- the visitor's location
  function permissionGranted() {
    if (!navigator.permissions || !navigator.permissions.query) return Promise.resolve(false);
    return navigator.permissions
      .query({ name: 'geolocation' })
      .then((p) => p.state === 'granted')
      .catch(() => false);
  }
  async function requestHere(field) {
    S.wantHere = field;
    combos[field].setText({ kind: 'here' });
    S[field] = null;
    if (await permissionGranted()) return locate(field);
    clearMsgs();
    setState('locate-ask');
    hideResult();
    el('dp-ask').hidden = false;
    announce('To start from where you are, your browser will ask to share your location. Choose Continue or Not now.');
    el('dp-ask-yes').focus();
  }
  function locate(field) {
    el('dp-ask').hidden = true;
    status('locate-wait', 'Finding your location…');
    if (!navigator.geolocation) return locateFailed(field);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        if (S.wantHere !== field) return;
        S.wantHere = false;
        setSelection(field, { kind: 'here', pt: [pos.coords.latitude, pos.coords.longitude] });
      },
      () => locateFailed(field),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
  }
  function locateFailed(field) {
    S.wantHere = false;
    S[field] = null;
    combos[field].setText(null);
    problem('locate-denied', 'We could not find your location. Choose a start instead.');
    fieldEls[field].focus();
  }
  el('dp-ask-yes').onclick = () => locate(S.wantHere || 'from');
  el('dp-ask-no').onclick = () => {
    const f = S.wantHere || 'from';
    S.wantHere = false;
    combos[f].setText(null);
    status('empty', '');
    el('dp-empty').hidden = false;
    fieldEls[f].focus();
  };

  // ---------------------------------------------------------------- pick on map
  function startPick(field) {
    S.picking = field;
    clearMsgs();
    setState('picking');
    root.dataset.picking = '1';
    document.body.classList.add('dp-picking');
    el('dp-pick-text').textContent = field === 'from' ? 'Tap the map to choose your start.' : 'Tap the map to choose your destination.';
    el('dp-pick').hidden = false;
    announce(el('dp-pick-text').textContent);
    map.getContainer().style.cursor = 'crosshair';
    map.once('click', onPick);
    el('dp-pick-cancel').focus();
  }
  function onPick(e) {
    if (!S.picking) return;
    const f = S.picking;
    endPick();
    setSelection(f, { kind: 'map', pt: [e.latlng.lat, e.latlng.lng] });
    announce(`${f === 'from' ? 'Start' : 'Destination'} set on the map.`);
  }
  function endPick() {
    S.picking = null;
    delete root.dataset.picking;
    document.body.classList.remove('dp-picking');
    map.getContainer().style.cursor = '';
    map.off('click', onPick);
  }
  el('dp-pick-cancel').onclick = () => {
    const f = S.picking;
    endPick();
    update();
    if (f) fieldEls[f].focus();
  };

  // ---------------------------------------------------------------- map drawing
  const layer = L.layerGroup();
  let hlLine = null;
  let stepMarks = [];
  const pinIcon = (cls, label, glyph) =>
    L.divIcon({
      className: '',
      iconSize: [40, 40],
      iconAnchor: [20, 20],
      html: `<div class="dp-pin ${cls}"><span class="dp-disc">${glyph}</span><span class="dp-lab">${label}</span></div>`,
    });
  function drawPins() {
    layer.clearLayers();
    hlLine = null;
    stepMarks = [];
    if (!S.open) return;
    layer.addTo(map);
    if (S.from) L.marker(S.from.pt, { icon: pinIcon('start', 'Start', svg('pin')), interactive: false, keyboard: false, zIndexOffset: 900 }).addTo(layer);
    if (S.to) L.marker(S.to.pt, { icon: pinIcon('end', 'End', svg('flag')), interactive: false, keyboard: false, zIndexOffset: 900 }).addTo(layer);
  }
  function drawRoute(r) {
    drawPins();
    const pts = r.line.map((c) => [c[1], c[0]]);
    L.polyline(pts, { className: 'dp-casing', color: '#ffffff', weight: 11, opacity: 1, lineCap: 'round', lineJoin: 'round', interactive: false }).addTo(layer);
    hlLine = L.polyline([], { className: 'dp-hl', color: '#f59e0b', weight: 15, opacity: 0.95, lineCap: 'round', interactive: false }).addTo(layer);
    L.polyline(pts, { className: 'dp-line', color: '#1e40af', weight: 6, opacity: 1, lineCap: 'round', lineJoin: 'round', interactive: false }).addTo(layer);
    // small signs on the route for crossings and cautions; each also says so in the step text
    r.stepList.forEach((s, i) => {
      if (s.kind !== 'cross' && !s.warnings.length) return;
      const mid = pts[Math.floor((s.fromIdx + s.toIdx) / 2)];
      const caution = s.warnings.length > 0 && s.warnings.some((w) => w !== 'crossing-not-audible');
      const m = L.marker(mid, {
        icon: L.divIcon({
          className: '',
          iconSize: [26, 26],
          iconAnchor: [13, 13],
          html: `<span class="dp-sign ${caution ? 'warn' : ''}" aria-hidden="true">${svg(s.kind === 'cross' ? 'cross' : 'warn')}</span>`,
        }),
        keyboard: false,
        title: `Step ${i + 1}`,
      }).addTo(layer);
      m.on('click', () => selectStep(i, { focus: true }));
      stepMarks.push(m);
    });
  }
  function clearRoute() {
    layer.clearLayers();
    hlLine = null;
    stepMarks = [];
    if (S.open && (S.from || S.to)) drawPins();
  }
  function padding() {
    if (PHONE.matches) {
      const h = root.getBoundingClientRect().height;
      return { paddingTopLeft: [24, 24], paddingBottomRight: [24, h + 16] };
    }
    return { padding: [56, 56] };
  }
  function fit(latlngs, maxZoom) {
    if (!latlngs.length) return;
    const b = L.latLngBounds(latlngs);
    map.fitBounds(b, { ...padding(), maxZoom: maxZoom || 19, animate: !REDUCED.matches });
  }

  // ---------------------------------------------------------------- routing
  async function update(opts) {
    opts = opts || {};
    const mine = ++S.token;
    if (S.picking || S.wantHere) return;
    drawPins();
    if (!S.from || !S.to) {
      hideResult();
      status('empty', '');
      el('dp-empty').hidden = false;
      el('dp-empty').textContent = S.from || S.to ? `Now choose ${S.from ? 'where you are going' : 'where you are starting'}.` : 'Choose where you are starting and where you are going.';
      return;
    }
    fit([S.from.pt, S.to.pt], 17); // both ends in view, whatever happens next
    const sameSpot =
      (S.from.kind === 'place' && S.to.kind === 'place' && S.from.it === S.to.it) ||
      Math.hypot((S.from.pt[0] - S.to.pt[0]) * 111320, (S.from.pt[1] - S.to.pt[1]) * 85000) < 8;
    if (sameSpot) {
      problem('same', 'You are already there.');
      return;
    }
    const rf = regionOf(S.from);
    const rt = regionOf(S.to);
    const region = S.to.kind === 'place' ? rt : rf || rt;
    if ((S.from.kind === 'place' && S.to.kind === 'place' && rf !== rt) || (rf && rt && rf !== rt)) {
      problem('mixed', 'These two places are in different cities. Choose a start and a destination in the same city.', googleLinkHtml());
      return;
    }
    if (!region || !enabledRegions.has(region)) {
      problem('unavailable', 'Step-by-step walking routes are not available for this area yet. You can open the route in Google Maps.', googleLinkHtml());
      return;
    }
    const be = backendFor(region);
    if (be.state !== 'ready') {
      status('loading', 'Loading walking map…');
      hideResult();
      try {
        await be.start();
      } catch (err) {
        if (mine !== S.token) return;
        problem('load-error', 'We could not load the walking map. Try again, or open this in Google Maps.', `<div class="dp-btns"><button type="button" class="primary" id="dp-retry">Try again</button>${googleLinkHtml()}</div>`);
        const retry = el('dp-retry');
        retry.onclick = () => {
          be.promise = null;
          be.state = 'idle';
          update(opts);
        };
        retry.focus();
        return;
      }
      if (mine !== S.token) return;
    }
    status('searching', 'Finding the easiest step-free route…');
    announce('Finding the easiest step-free route…');
    let r;
    try {
      r = await be.route([S.from.pt[0], S.from.pt[1], S.to.pt[0], S.to.pt[1], S.profile]);
    } catch (err) {
      if (mine !== S.token) return;
      problem('load-error', 'Something went wrong while finding the route. Try again, or open this in Google Maps.', `<div class="dp-btns"><button type="button" class="primary" id="dp-retry">Try again</button>${googleLinkHtml()}</div>`);
      el('dp-retry').onclick = () => update(opts);
      return;
    }
    if (mine !== S.token) return;
    if (r.error === 'too_far') {
      const which = r.which === 'from' ? 'The start' : 'The destination';
      problem('too-far', `${which} is more than 500 feet from a mapped path. Try a point on a sidewalk or street.`, googleLinkHtml());
      fieldEls[r.which].focus();
      return;
    }
    if (r.error === 'no_route') {
      problem('no-route', 'We found no step-free route between these points in the map data. Stairs or a missing sidewalk may be in the way. Try a different start, or call ahead.', `<div class="dp-btns"><span id="dp-err-report"></span>${googleLinkHtml()}</div>`);
      attachReport(el('dp-err-report'));
      return;
    }
    if (r.length_feet === 0 || r.nodes.length < 2) {
      problem('same', 'You are already there.');
      return;
    }
    showResult(r, opts);
  }
  function onSelectionsChanged() {
    update();
  }

  // ---------------------------------------------------------------- the result
  function doorNote() {
    if (!S.to || S.to.kind !== 'place' || S.to.door) return '';
    return S.to.noDoorKnown
      ? "The route ends at the building's mapped location; no accessible door is mapped. Check with the venue for an accessible entrance."
      : "The route ends at the place's mapped location. Check with the venue for an accessible entrance.";
  }
  function shareLink() {
    const to = U.token(S.to);
    const from = S.from.kind === 'here' ? 'here' : U.token(S.from);
    return location.href.split('#')[0] + U.formatHash(from, to, S.profile);
  }
  function showResult(r, opts) {
    clearMsgs();
    setState('route');
    root.classList.remove('is-error');
    S.result = r;
    S.step = -1;
    const fromName = nameOf(S.from);
    const toName = nameOf(S.to);
    S.model = { result: r, fromName, toName, doorNote: doorNote(), link: null };
    const sum = el('dp-sum-h');
    sum.textContent = `${U.timeText(r.length_feet)[0].toUpperCase()}${U.timeText(r.length_feet).slice(1)} · ${U.distText(r.length_feet)}`;
    el('dp-fromto').innerHTML = `<span class="vh">Route </span>${esc(fromName)} <span aria-hidden="true">→</span><span class="vh"> to </span> ${esc(toName)}<br><span class="dp-prof">${U.PROFILE_LABEL[S.profile]} route</span>`;
    const facts = [`<li class="ok">${svg('check')}<span>No stairs</span></li>`, `<li>${svg('cross')}<span>${esc(r.crossings_text)}</span></li>`];
    if (r.steep_sections) facts.push(`<li class="warn">${svg('warn')}<span><strong>Caution:</strong> ${r.steep_sections} short section${r.steep_sections > 1 ? 's' : ''} steeper than a ramp</span></li>`);
    if (r.road_without_sidewalk_feet > 50) facts.push(`<li class="warn">${svg('warn')}<span><strong>Caution:</strong> about ${r.road_without_sidewalk_feet} feet on a road with no sidewalk mapped</span></li>`);
    if (r.raised_kerbs) facts.push(`<li class="warn">${svg('warn')}<span><strong>Caution:</strong> ${r.raised_kerbs} raised curb${r.raised_kerbs > 1 ? 's' : ''} mapped on the way</span></li>`);
    el('dp-facts').innerHTML = facts.join('');
    el('dp-compare').textContent = r.compared_with_shortest;
    el('dp-note').innerHTML = `${esc(NOT_CHECKED)} <span class="dp-est">Time is an estimate at ${U.PACE_MPH} mph.</span>`;
    el('dp-steps').innerHTML =
      r.stepList
        .map(
          (s, i) =>
            `<li><button type="button" class="dp-step" data-i="${i}" aria-current="false">${svg(ICON[s.kind] ? s.kind : 'straight', 'dir')}<span class="dp-st"><span class="vh">Step ${i + 1}: </span>${s.warnings.length ? stepCaution(s) : ''}${esc(s.text)}</span></button></li>`
        )
        .join('') +
      `<li class="dp-arrive">${svg('flag', 'dir')}<span class="dp-st"><span class="vh">Last step: </span>Arrive at ${esc(toName)}.</span></li>`;
    const dn = el('dp-doornote');
    const note = doorNote();
    dn.hidden = !note;
    dn.textContent = note;
    el('dp-stepof').textContent = `${r.stepList.length + 1} steps`;
    el('dp-google').href = U.googleUrl(S.from.pt, S.to.pt);
    attachReport(el('dp-report-slot'));
    if (!S.keepHeight) S.height = PHONE.matches ? 'summary' : 'steps'; // phone: map first, steps one tap away
    setSteps(S.height !== 'summary');
    el('dp-result').hidden = false;
    drawRoute(r);
    fit(r.line.map((c) => [c[1], c[0]]));
    const summaryText = `Route found. ${sum.textContent}. No stairs. ${r.crossings_text} ${r.compared_with_shortest} ${NOT_CHECKED}`;
    announce(summaryText);
    if (opts && opts.focus === false) return;
    sum.focus({ preventScroll: false });
    el('dp-scroll').scrollTop = 0;
  }
  function stepCaution(s) {
    const labels = [];
    if (s.warnings.includes('crossing-no-signal')) labels.push('no signal');
    if (S.profile === 'blind' && s.warnings.includes('crossing-not-audible')) labels.push('no audible signal');
    if (s.warnings.includes('steep')) labels.push('steep');
    if (s.warnings.includes('no-sidewalk')) labels.push('no sidewalk');
    return labels.length ? `<strong class="dp-caution">${svg('warn')}Caution: ${labels.join(', ')}.</strong> ` : '';
  }
  function selectStep(i, opts) {
    const r = S.result;
    if (!r) return;
    const n = r.stepList.length;
    i = Math.max(0, Math.min(n - 1, i));
    S.step = i;
    const s = r.stepList[i];
    root.querySelectorAll('.dp-step').forEach((b) => b.setAttribute('aria-current', +b.dataset.i === i ? 'step' : 'false'));
    const pts = r.line.slice(s.fromIdx, s.toIdx + 1).map((c) => [c[1], c[0]]);
    if (hlLine) hlLine.setLatLngs(pts);
    fit(pts, 18);
    el('dp-stepof').textContent = `Step ${i + 1} of ${n + 1}`;
    el('dp-prev').disabled = i === 0;
    el('dp-next').disabled = i === n - 1;
    announce(`Step ${i + 1} of ${n + 1}: ${s.text}`);
    const btn = root.querySelector(`.dp-step[data-i="${i}"]`);
    if (btn) {
      if (opts && opts.focus) btn.focus({ preventScroll: true });
      btn.scrollIntoView({ block: 'nearest' });
    }
  }
  el('dp-steps').addEventListener('click', (e) => {
    const b = e.target.closest('.dp-step');
    if (b) selectStep(+b.dataset.i);
  });
  el('dp-prev').onclick = () => selectStep(S.step < 0 ? 0 : S.step - 1);
  el('dp-next').onclick = () => selectStep(S.step + 1);

  // phone sheet heights: summary | steps | full
  function setSteps(open) {
    S.height = open ? (S.height === 'full' ? 'full' : 'steps') : 'summary';
    root.dataset.height = S.height;
    const t = el('dp-toggle-steps');
    t.setAttribute('aria-expanded', String(S.height !== 'summary'));
    t.querySelector('span').textContent = S.height === 'summary' ? 'Steps' : 'Map';
    t.querySelector('svg').innerHTML = S.height === 'summary' ? ICON.up : ICON.down;
    el('dp-expand').setAttribute('aria-pressed', String(S.height === 'full'));
    el('dp-expand').textContent = S.height === 'full' ? 'Smaller list' : 'Full list';
    if (PHONE.matches && S.result) requestAnimationFrame(() => fit(S.result.line.map((c) => [c[1], c[0]])));
  }
  el('dp-toggle-steps').onclick = () => {
    S.keepHeight = true;
    setSteps(S.height === 'summary');
  };
  el('dp-expand').onclick = () => {
    S.keepHeight = true;
    S.height = S.height === 'full' ? 'steps' : 'full';
    setSteps(true);
  };
  el('dp-change').onclick = () => {
    root.dataset.height = 'form';
    root.classList.add('editing');
    fieldEls.from.focus();
  };

  // ---------------------------------------------------------------- actions
  function say(text) {
    announce(text);
    el('dp-status').textContent = text;
  }
  function copy(text, done, fallback) {
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject(new Error('no clipboard')))
      .then(() => say(done))
      .catch(() => {
        const box = el('dp-status');
        box.textContent = fallback;
        announce(fallback);
      });
  }
  el('dp-copy-text').onclick = () => {
    if (!S.result) return;
    S.model.link = shareLink();
    copy(U.routeText(S.model), 'Directions copied.', 'Your browser would not let us copy. Select the steps and copy them by hand.');
  };
  el('dp-copy-link').onclick = () => {
    if (!S.from || !S.to) return;
    const url = shareLink();
    copy(url, S.from.kind === 'here' ? 'Link copied. It does not include your location; it starts from My location for whoever opens it.' : 'Link copied.', `Copy this link: ${url}`);
  };
  function attachReport(slot) {
    if (!slot) return;
    slot.replaceChildren();
    const ctxR = {
      link_id: S.to && S.to.kind === 'place' ? S.to.it.p.link_id : null,
      name: `Route from ${nameOf(S.from)} to ${nameOf(S.to)} (${S.profile})`.slice(0, 160),
      region: (S.to && regionOf(S.to)) || null,
    };
    if (ctx.reportButton && ctx.RATECFG) {
      slot.append(ctx.reportButton(ctxR, 'Report a problem'));
    }
    const issue =
      'https://github.com/zenaism/accessibility-map/issues/new?title=' +
      encodeURIComponent('Route problem: ' + ctxR.name) +
      '&body=' +
      encodeURIComponent(`Route: ${ctxR.name}\nLink: ${S.from && S.to && S.from.kind !== 'here' ? shareLink() : location.href}\n\nWhat is wrong? (for example: a missing ramp, a blocked path, a crossing that is not there)\n\n`);
    const a = document.createElement('a');
    a.className = 'btn ghost';
    a.href = issue;
    a.target = '_blank';
    a.rel = 'noopener';
    a.setAttribute('data-report-fallback', '');
    a.innerHTML = 'Report a problem<span class="vh"> with this route (opens GitHub in a new tab)</span>';
    slot.append(a);
    ctx.reportShow(); // shows the in-app form button when the database answers, else this link
  }

  // ---------------------------------------------------------------- profile, swap
  root.querySelectorAll('input[name=dp-profile]').forEach((r) => {
    r.checked = r.value === S.profile;
    r.addEventListener('change', () => {
      S.profile = r.value;
      store.set('atlas-route-profile', S.profile);
      helpText();
      announce(`${U.PROFILE_LABEL[S.profile]} route selected.`);
      if (S.from && S.to) update({ focus: false });
    });
  });
  function helpText() {
    el('dp-profile-help').textContent =
      S.profile === 'blind'
        ? 'Prefers crossings with traffic signals, ideally audible, and avoids unmarked ones. Steps say what each crossing has.'
        : 'Avoids stairs, steep sections, rough surfaces and raised curbs.';
  }
  helpText();
  el('dp-swap').onclick = () => {
    const a = S.from;
    const b = S.to;
    if (a && a.kind === 'here') {
      // "My location" can only be a start
      S.from = b;
      S.to = null;
    } else {
      S.from = b;
      S.to = a;
    }
    combos.from.setText(S.from);
    combos.to.setText(S.to);
    announce('Start and destination swapped.');
    update();
  };

  // ---------------------------------------------------------------- opening and closing
  const dirBtn = document.createElement('button');
  dirBtn.type = 'button';
  dirBtn.id = 'dir-open';
  dirBtn.className = 'primary';
  dirBtn.setAttribute('aria-controls', 'dirp');
  dirBtn.setAttribute('aria-expanded', 'false');
  dirBtn.innerHTML = `${svg('google').replace('<path d="M13 3l4 0 0 4M17 3l-5 5"/>', '')}Directions`;
  const near = document.getElementById('near');
  near.before(dirBtn);
  const prefetch = () => {
    const first = [...enabledRegions][0];
    if (first && !backends[first]) backendFor(first).start().catch(() => {});
  };
  dirBtn.addEventListener('pointerenter', prefetch, { once: true });
  dirBtn.addEventListener('focus', prefetch, { once: true });
  dirBtn.addEventListener('click', () => openPanel({ opener: dirBtn }));

  function openPanel(o) {
    o = o || {};
    const wasOpen = S.open;
    if (!wasOpen) S.opener = o.opener || document.activeElement;
    S.open = true;
    root.hidden = false;
    dirBtn.setAttribute('aria-expanded', 'true');
    document.body.classList.add('dp-open');
    const side = document.getElementById('side');
    if (side) side.inert = true;
    if (PHONE.matches) ctx.setSheet(false);
    else ctx.setList(true);
    if (o.profile) {
      S.profile = o.profile === 'blind' ? 'blind' : 'wheelchair';
      root.querySelectorAll('input[name=dp-profile]').forEach((r) => (r.checked = r.value === S.profile));
      helpText();
    }
    if (o.to) {
      S.to = o.to;
      combos.to.setText(o.to);
    }
    if (o.from) {
      S.from = o.from;
      combos.from.setText(o.from);
    }
    drawPins();
    if (o.to && !S.from && !o.from) {
      requestHere('from'); // plan: From starts as My location; the browser is asked only now, after a short explanation
      return;
    }
    if (S.from && S.to) {
      update();
    } else if (!wasOpen || !S.result) {
      status('empty', '');
      el('dp-empty').hidden = false;
      (S.from ? fieldEls.to : fieldEls.from).focus();
    }
  }
  function closePanel(opts) {
    if (!S.open) return;
    endPick();
    S.open = false;
    S.wantHere = false;
    S.token++;
    root.hidden = true;
    root.classList.remove('editing');
    dirBtn.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('dp-open', 'dp-has-route');
    const side = document.getElementById('side');
    if (side) side.inert = false;
    layer.clearLayers();
    if (map.hasLayer(layer)) map.removeLayer(layer);
    const back = (opts && opts.returnTo) || S.opener;
    S.opener = null;
    if (back && document.contains(back) && !back.hidden) back.focus();
    else dirBtn.focus();
  }
  el('dp-back').onclick = () => closePanel();
  root.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape' || e.defaultPrevented) return;
    if (S.picking) {
      el('dp-pick-cancel').click();
      return;
    }
    e.preventDefault();
    closePanel();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && S.picking) el('dp-pick-cancel').click();
  });

  // ---------------------------------------------------------------- route links, cards, popups
  function selFromToken(tok) {
    if (!tok) return null;
    if (tok === 'here') return { kind: 'here', pt: null, pending: true };
    const pt = U.parsePoint(tok);
    if (pt) return { kind: 'map', pt };
    const it = ITEMS.find((x) => x.p.link_id === tok);
    return it ? placeSel(it) : null;
  }
  function openFromHash() {
    const h = U.parseHash(location.hash);
    if (!h) return false;
    const to = selFromToken(h.to);
    const from = selFromToken(h.from);
    if (!to || to.pending) {
      openPanel({ opener: dirBtn, profile: h.profile });
      problem('empty', 'We could not find the destination in this link. Choose a destination.');
      return true;
    }
    if (from && from.pending) openPanel({ opener: dirBtn, profile: h.profile, to });
    else openPanel({ opener: dirBtn, profile: h.profile, to, from });
    return true;
  }
  window.addEventListener('hashchange', openFromHash);

  window.AtlasRouting = {
    open(o) {
      o = o || {};
      const it = o.toPlaceId != null ? ITEMS.find((x) => x.p.link_id === o.toPlaceId || String(x.i) === String(o.toPlaceId)) : null;
      const from = o.fromLatLng ? { kind: 'map', pt: [o.fromLatLng[0], o.fromLatLng[1]] } : null;
      openPanel({ opener: document.activeElement, to: it ? placeSel(it) : null, from, profile: o.profile });
      return !!it || !o.toPlaceId;
    },
    close: closePanel,
    isReady() {
      const first = [...enabledRegions][0];
      return !!first && !!backends[first] && backends[first].state === 'ready';
    },
    stats,
    get state() {
      return S.state;
    },
    get result() {
      return S.result;
    },
  };
  window.addEventListener('atlas:route-to', (e) => {
    const d = (e && e.detail) || {};
    window.AtlasRouting.open({ toPlaceId: d.placeId, profile: d.profile, fromLatLng: d.fromLatLng });
  });

  // "Route here" on place cards and map popups; the old Google Maps link becomes the secondary choice
  const routeBtn = (it) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'ghost dp-route-btn';
    b.innerHTML = `Route here<span class="vh"> to ${esc(it.p.name)}</span>`;
    b.onclick = () => openPanel({ opener: b, to: placeSel(it) });
    return b;
  };
  ctx.decorateCard = (li, it) => {
    if (!routable(it)) return;
    const g = li.querySelector('a[href*="google.com/maps/dir"]');
    const b = routeBtn(it);
    if (g) {
      g.replaceWith(b);
      li.dataset.gmaps = g.href;
    } else li.querySelector('.actions').prepend(b);
  };
  ctx.decorateDetails = (box, it) => {
    if (!routable(it)) return;
    const links = box.querySelector('.links');
    if (!links || links.querySelector('.dp-gmaps')) return;
    const sel = placeSel(it);
    const a = document.createElement('a');
    a.className = 'btn ghost dp-gmaps';
    a.target = '_blank';
    a.rel = 'noopener';
    a.href = `https://www.google.com/maps/dir/?api=1&destination=${sel.pt[0]},${sel.pt[1]}&travelmode=walking`;
    a.innerHTML = `Directions in Google Maps<span class="vh"> to ${esc(it.p.name)} (opens in a new tab)</span>`;
    links.prepend(a);
  };
  ctx.decoratePopup = (el2, it) => {
    if (!routable(it)) return;
    const row = el2.querySelector('.pop-actions');
    if (row) row.prepend(routeBtn(it));
  };

  // the first thing to do on a page that was opened with a route link
  if (location.hash.startsWith('#route=')) setTimeout(openFromHash, 0);
  return ctx;
}
