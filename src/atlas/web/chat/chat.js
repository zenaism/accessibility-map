/* Openway Assistant chat (session B3): the Harbor chat screen on the B0 foundation.
   Openway.chat.mount(root, {base, mapHref, region}) wires the page skeleton built by atlas.assistant.page:
   header, settings, conversation (role=log), compose area A (one field, icons inside), voice bar, tab bar.
   Engine and answer pieces: Openway.engine (guided, local), Openway.composer; speech in: Openway.speech; out: Openway.voice. */
(function (g) {
  'use strict';
  const O = (g.Openway = g.Openway || {});
  const doc = g.document, ui = g.atlas.ui;
  const h = (tag, props, ...kids) => {
    const el = doc.createElement(tag);
    for (const k of Object.keys(props || {})) {
      const v = props[k];
      if (v === null || v === undefined || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (v === true) el.setAttribute(k, '');
      else el.setAttribute(k, v);
    }
    for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) el.append(kid.nodeType ? kid : doc.createTextNode(String(kid)));
    return el;
  };
  const ic = (name, cls) => { const t = doc.createElement('template'); t.innerHTML = ui.icon(name, cls || ''); return t.content.firstChild; };
  const RK = { accessible: 'yes', partial: 'partial', not_accessible: 'no', unknown: 'unknown' };
  const WORD = { yes: 'Accessible', partial: 'Partly accessible', no: 'Not accessible', unknown: 'Not known' };
  const badge = (rating) => { const k = RK[rating] || 'unknown'; return h('span', { class: 'badge ' + k }, ic(k), h('span', { text: WORD[k] })); };
  const store = {
    mem: {}, ok: null,
    get(k) { try { const v = g.localStorage.getItem(k); this.ok = true; return v; } catch (e) { this.ok = false; return this.mem[k] === undefined ? null : this.mem[k]; } },
    set(k, v) { this.mem[k] = v; try { g.localStorage.setItem(k, v); this.ok = true; } catch (e) { this.ok = false; } },
    del(k) { delete this.mem[k]; try { g.localStorage.removeItem(k); } catch (e) { /* blocked */ } },
  };
  const readJSON = (k, d) => { try { const v = store.get(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } };
  const LAYER_NAME = { culture: 'Museum', park: 'Park', restroom: 'Restroom', adaptive_recreation: 'Recreation', lodging: 'Lodging', event: 'Event venue', building: 'Building', food_drink: 'Food and drink', service: 'Shop', trail: 'Trail' };
  const SIZES = [['1', 'Normal'], ['1.25', 'Large'], ['1.5', 'Extra large']];
  const MOBILITY = [['manual', 'Manual wheelchair'], ['power', 'Power chair'], ['cane', 'Cane or guide'], ['other', 'Something else'], ['', 'Prefer not to say']];
  const STEPS = [['cannot', 'No, I cannot use steps'], ['some', 'A few steps are fine'], ['', 'Not sure']];
  const RELY = [['screen_reader', 'A screen reader'], ['large_text', 'Large text'], ['voice', 'Speaking and listening']];
  const SUGGEST = [
    ['Restroom near me', 'Where is the closest accessible restroom?'], ['Art Museum wheelchairs', 'Can I borrow a wheelchair at the Cincinnati Art Museum?'],
    ['Findlay Market restroom', 'Does Findlay Market have an accessible restroom?'], ['Accessible parking', 'Where is accessible parking near me?'],
    ['Step-free food', 'Find food with no steps at the door'], ['Trails', 'What paved trails are there?'],
  ];
  const fmtClock = (s) => Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');

  function deviceToday() {
    const q = new URLSearchParams(g.location.search).get('today');
    if (g.__OPENWAY_TODAY) return g.__OPENWAY_TODAY;
    if (q && /^\d{4}-\d{2}-\d{2}$/.test(q)) return q;
    const d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  function mount(root, options) {
    options = options || {};
    const base = options.base === undefined ? 'assistant/' : options.base;
    const $ = (sel) => root.querySelector(sel);
    const log = $('#ch-log'), input = $('#q'), form = $('#ch-form'), sendBtn = $('#ch-send'), micBtn = $('#ch-mic'), photoBtn = $('#ch-photo');
    const settingsEl = $('#settings'), settingsBtn = $('#ch-settings-btn'), live = $('#ch-live'), hintEl = $('#ch-hint'), voiceHost = $('#ch-voice'), banner = $('#ch-banner'), fileInput = $('#ch-file'), modeEl = $('#ch-mode');
    const REGS = g.__REGIONS || [], regShort = (id) => (REGS.find((r) => r.id === id) || {}).short || id;
    const validRegion = (id) => (REGS.some((r) => r.id === id) ? id : null);
    const chosenRegion = () => validRegion(new URLSearchParams(g.location.search).get('region')) || validRegion(store.get('atlas-region'));
    // Use the model? 'local' = the person chose it; 'auto' (no choice yet) = yes only when the page was built for an online model.
    const wantsModel = () => S.prefs.engine === 'local' || (S.prefs.engine === 'auto' && !!(S.health && S.health.hosted));
    const S = { region: null, prefs: Object.assign({ size: '1', plain: false, engine: 'auto', rate: '1' }, readJSON('openway.prefs', {})), needs: readJSON('openway.needs', {}), turns: [], toldOnline: false, location: null, busy: false, ctrl: null, guided: null, local: null, health: null, image: null, lastQ: null, answers: 0, speaking: null, voice: 'idle', voiceInfo: {} };
    S.region = chosenRegion();
    const rules = () => O.rules;
    const say = (t) => { live.textContent = ''; g.setTimeout(() => { live.textContent = t; }, 40); };
    const hint = (t) => { hintEl.textContent = t || ''; hintEl.hidden = !t; };
    // which city the answers are about: always said in plain words under the title (not a control)
    const cityLine = $('#ch-city-line');
    function setCityLine(other) {
      const fullNames = REGS.filter((r) => r.tier === 'full').map((r) => r.short);
      cityLine.textContent = other ? 'Showing ' + regShort(other) + ' for this question' : S.region ? 'Answering for ' + regShort(S.region) : 'Answering for ' + (fullNames.join(' and ') || 'our cities');
    }
    setCityLine();
    g.addEventListener('storage', (e) => { if (e.key === 'atlas-region') { S.region = chosenRegion(); setCityLine(); } });
    document.addEventListener('atlas:region-changed', (e) => { S.region = validRegion(e.detail && e.detail.region); setCityLine(); });
    const savePrefs = () => store.set('openway.prefs', JSON.stringify(S.prefs));
    const applySize = () => { root.style.setProperty('--ch-scale', S.prefs.size); };
    applySize();
    const fire = (name, detail) => !g.dispatchEvent(new g.CustomEvent(name, { detail, cancelable: true }));
    const regionOf = (pid) => { const p = S.guided && S.guided.kb.byId.get(pid); return p ? p.region : S.region || options.region || null; };
    const mapUrl = (pid) => (options.mapBase || '') + regionOf(pid) + '.html#place=' + encodeURIComponent(pid);
    const ctxNow = () => {
      const n = S.needs || {}, needs = {};
      if (n.mobility) needs.mobility = n.mobility;
      if (n.steps) needs.steps = n.steps;
      if (n.rely && n.rely.length) needs.rely = n.rely.slice();
      return { today: deviceToday(), region: S.region || options.region || null, location: S.location, needs, plain: !!S.prefs.plain };
    };
    // a finished answer can be taller than the list: show its start (your question and the sentence), not its end
    const scrollToAnswer = (el) => { try { (el.previousElementSibling || el).scrollIntoView({ block: 'start', behavior: 'auto' }); } catch (e) { /* old browser */ } };
    const scrollEnd = (el) => { try { el.scrollIntoView({ block: 'nearest', behavior: 'auto' }); } catch (e) { /* old browser */ } };

    // ---- layout: the compose area stays above the bottom edge, also with the on-screen keyboard (visualViewport) ----
    const vv = g.visualViewport;
    function layout() {
      if (!vv) return;
      root.style.setProperty('--app-h', Math.round(vv.height) + 'px');
      root.style.setProperty('--app-top', Math.round(vv.offsetTop) + 'px');
      root.toggleAttribute('data-kb', g.innerHeight - vv.height > 120);
      if (doc.activeElement === input) scrollEnd(input);
    }
    if (vv) { vv.addEventListener('resize', layout); vv.addEventListener('scroll', layout); layout(); }
    input.addEventListener('focus', () => g.setTimeout(layout, 250));
    const grow = () => { if (input.readOnly) return; input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 110) + 'px'; };
    input.addEventListener('input', () => { grow(); sendBtn.removeAttribute('aria-disabled'); });

    // ---- offline ----
    function netState() {
      banner.textContent = '';
      if (g.navigator.onLine === false) {
        banner.append(h('div', { class: 'banner offline-banner', role: 'status' }, ic('offline'), h('span', { text: 'You are offline. Answers still work from data on this device. Voice and the map need a connection.' })));
      }
    }
    g.addEventListener('online', () => { netState(); say('You are back online.'); });
    g.addEventListener('offline', () => { netState(); say('You are offline. Answers still work from data on this device.'); });
    netState();

    // ---- settings ----
    function seg(name, legend, items, current, onchange, disabled) {
      const fs = h('fieldset', {}, h('legend', { text: legend }));
      const box = h('div', { class: 'seg' });
      for (const [val, label] of items) box.append(h('label', {}, h('input', { type: 'radio', name, value: val, checked: String(current) === String(val), disabled: disabled && disabled[val], onchange: () => onchange(val) }), h('span', { class: 'o' }, ic('check', 'tick'), label)));
      fs.append(box);
      return fs;
    }
    function toggleRow(label, on, onchange) {
      const id = 'sw' + Math.random().toString(36).slice(2, 7);
      const btn = h('button', { type: 'button', class: 'toggle', role: 'switch', 'aria-checked': String(!!on), 'aria-labelledby': id }, h('span', { class: 'track' }, h('span', { class: 'knob' }, ic('check'))));
      btn.addEventListener('atlas:switch', (e) => onchange(e.detail.checked));
      return h('div', { class: 'sw-row' }, h('span', { id, text: label }), btn);
    }
    function buildSettings() {
      settingsEl.textContent = '';
      const reach = !!(S.health && S.health.reachable);
      const hosted = !!(S.health && S.health.hosted);
      const eh = !S.health ? 'Checking for a local model…' : !S.health.reachable ? 'The local model is not available here. Guided mode answers from saved data on this device and sends nothing anywhere.'
        : hosted ? (S.health.model ? 'The online model sends your question and the last few messages of this chat to our server and to a model service. Nothing is saved there. Facts about places still come only from the saved data.' : 'The online model is not available right now. Guided mode still works.')
        : !S.health.model ? 'The local server is running, but no model is loaded. Start Ollama to use it. Guided mode still works.' : 'The local model runs on this computer. Answers are still checked against the saved data.';
      const engine = seg('engine', 'How I answer', [['guided', 'Guided (no model)'], ['local', hosted ? 'Online model' : 'Local model']], wantsModel() ? 'local' : 'guided', (v) => { S.prefs.engine = v; savePrefs(); refreshMode(); buildSettings(); }, { local: !reach });
      engine.append(h('p', { class: 'hint small', text: eh }));
      const size = seg('size', 'Text size', SIZES, S.prefs.size, (v) => { S.prefs.size = v; applySize(); savePrefs(); });
      const theme = h('fieldset', {}, h('legend', { text: 'Appearance' }),
        h('div', { class: 'seg' }, ['light', 'dark'].map((v) => h('label', {}, h('input', { type: 'radio', name: 'atlas-theme', value: v, checked: g.atlasTheme.get() === v }), h('span', { class: 'o' }, ic('check', 'tick'), ic(v === 'light' ? 'sun' : 'moon'), v === 'light' ? 'Light' : 'Dark')))),
        h('p', { class: 'hint small', text: 'Light is the default. Saved on this device for the map, reports and chat.' }));
      const gaps = readJSON('openway.gaps', []);
      const tools = h('div', { class: 'tools' },
        h('button', { type: 'button', class: 'btn btn-secondary', onclick: () => openNeeds() }, ic('settings'), 'My needs'),
        h('button', { type: 'button', class: 'btn btn-secondary', onclick: () => { toggleSettings(false); ask('What can you do?'); } }, ic('ask'), 'What can I ask?'),
        h('button', { type: 'button', class: 'btn btn-secondary', onclick: () => clearChat() }, ic('trash'), 'Clear conversation'));
      const note = h('p', { class: 'hint small' }, 'Nothing you type is sent anywhere in Guided mode. ',
        gaps.length ? [gaps.length + ' question' + (gaps.length > 1 ? 's' : '') + ' I could not answer ' + (gaps.length > 1 ? 'are' : 'is') + ' saved on this device only. ', h('button', { type: 'button', class: 'link', onclick: () => { store.del('openway.gaps'); buildSettings(); } }, 'Clear that list')] : '');
      settingsEl.append(engine, size, theme, toggleRow('Plain language (shorter sentences)', S.prefs.plain, (v) => { S.prefs.plain = v; savePrefs(); hint(v ? 'Plain language is on.' : ''); }),
        toggleRow('Use my location to sort by distance', !!S.location, (v) => { if (v) useLocation(); else { S.location = null; hint('Location is off.'); } }), tools, note);
    }
    function toggleSettings(force) {
      const open = force === undefined ? settingsEl.hidden : force;
      settingsEl.hidden = !open; settingsBtn.setAttribute('aria-expanded', String(open));
      if (open) { buildSettings(); checkHealth(); }
    }
    settingsBtn.addEventListener('click', () => toggleSettings());
    // Status lines for developers, in the browser console only. They never hold the question or the answer.
    function status(msg) { if (g.console && g.console.info) g.console.info('[Openway] ' + msg); }
    function refreshMode() { const local = wantsModel() && S.health && S.health.model; modeEl.textContent = local ? (S.health.hosted ? 'Online model' : 'Local model') : 'Guided mode'; }
    async function checkHealth() {
      if (!S.local) S.local = new O.engine.LocalEngine(options.serverBase || g.__OPENWAY_SERVER || '', null);
      const info = await S.local.info();
      S.health = { reachable: !info.error, model: !!info.model, models: info.models || [], hosted: !!info.hosted, vision: !!info.vision };
      status('model server ' + (S.local.base || '(this site)') + ': ' + (info.error ? info.error : (info.model ? 'ready, ' + (info.hosted ? 'online' : 'local') + ' model ' + (info.text_model || '') : 'reachable, but no model')) + '. Settings choice: ' + (wantsModel() ? 'model' : 'Guided (no model is called)') + '.');
      refreshMode(); if (!settingsEl.hidden) buildSettings();
    }

    // ---- My needs (a modal sheet from the foundation: focus trap, inert page, Escape) ----
    function openNeeds() {
      const n = S.needs || {};
      const opt = (type, name, v, label, on) => h('label', { class: 'opt' }, h('input', { type, name, value: v, checked: on }), h('span', { class: 'mk' + (type === 'checkbox' ? ' sq' : '') }, ic('check')), h('span', { text: label }));
      const group = (name, legend, items, cur) => h('fieldset', {}, h('legend', { text: legend }), ...items.map(([v, l]) => opt('radio', 'n-' + name, v, l, String(cur || '') === v)));
      const rely = h('fieldset', {}, h('legend', { text: '3. What do you rely on?' }), ...RELY.map(([v, l]) => opt('checkbox', 'n-rely', v, l, (n.rely || []).includes(v))));
      const node = h('form', { class: 'stack3', method: 'dialog' },
        h('p', { class: 'muted small', text: 'Three optional questions. They change which places I suggest. Your answers stay on this device only.' }),
        group('mobility', '1. How do you get around?', MOBILITY, n.mobility), group('steps', '2. Can you use steps?', STEPS, n.steps), rely,
        h('div', { class: 'dlg-foot' }, h('button', { type: 'button', class: 'btn btn-secondary', onclick: () => { clearNeeds(); sheet.close(); } }, 'Clear my answers'), h('button', { type: 'button', class: 'btn btn-secondary', 'data-sheet-close': true }, 'Skip'), h('button', { type: 'submit', class: 'btn btn-primary' }, 'Save')));
      const sheet = ui.sheet.open({ title: 'My needs', node });
      node.addEventListener('submit', (e) => {
        e.preventDefault();
        const val = (nm) => { const el = node.querySelector('input[name="n-' + nm + '"]:checked'); return el ? el.value : ''; };
        const r = Array.from(node.querySelectorAll('input[name="n-rely"]:checked')).map((x) => x.value);
        S.needs = { mobility: val('mobility'), steps: val('steps'), rely: r };
        store.set('openway.needs', JSON.stringify(S.needs));
        if (r.includes('large_text') && S.prefs.size === '1') { S.prefs.size = '1.25'; applySize(); savePrefs(); }
        const msg = store.ok === false ? 'Saved for this visit only: this browser blocks saving.' : 'Saved on this device.';
        hint('My needs: ' + msg); say('My needs ' + msg.toLowerCase()); sheet.close(); if (!settingsEl.hidden) { buildSettings(); settingsBtn.focus(); }
      });
      node.addEventListener('click', (e) => { const b = e.target.closest('[data-sheet-close]'); if (b && sheet.el.querySelector('[data-sheet-close]') !== b) sheet.el.querySelector('[data-sheet-close]').click(); });
    }
    function clearNeeds() { S.needs = {}; store.del('openway.needs'); hint('My needs cleared.'); say('My needs cleared.'); }

    // ---- location ----
    function useLocation() {
      if (!g.navigator.geolocation) { hint('Your browser cannot share your location. Tell me an area instead, such as downtown or uptown Oxford.'); return; }
      hint('Asking your browser for your location…');
      g.navigator.geolocation.getCurrentPosition((p) => { S.location = [Math.round(p.coords.latitude * 1e4) / 1e4, Math.round(p.coords.longitude * 1e4) / 1e4]; hint('Location is on. I use it only on this device to sort by distance.'); say('Location is on.'); },
        () => { S.location = null; hint('I could not get your location. You can tell me an area instead, such as downtown or uptown Oxford.'); }, { timeout: 10000, maximumAge: 60000 });
    }

    // ---- conversation ----
    const chips = (items, label, cls) => h('div', { class: cls || 'suggest', role: 'group', 'aria-label': label }, items.map(([l, m]) => h('button', { type: 'button', class: 'chip', onclick: () => ask(m), text: l })));
    function greeting() {
      log.textContent = '';
      log.append(h('div', { class: 'msg bot' }, h('h2', { class: 'vh', text: 'Assistant' }),
        h('div', { class: 'bubble bot', text: 'Hi. Ask me about a place in ' + (S.region ? regShort(S.region) : 'Cincinnati or Oxford') + '. I use saved data and tell you when I do not know.' }), chips(SUGGEST, 'Ideas')));
    }
    function emptyHistory() {
      log.textContent = '';
      log.append(h('div', { class: 'state' }, h('span', { class: 'big' }, ic('ask')), h('p', { class: 'lead', text: 'No messages yet' }), h('p', { class: 'muted', text: 'Ask about a place, or tap an idea.' }), chips(SUGGEST.slice(0, 4), 'Ideas')));
    }
    function clearChat() { cancel(); speech.reset(); setVoice('idle'); input.value = ''; grow(); emptyHistory(); S.answers = 0; S.turns = []; toggleSettings(false); say('Conversation cleared.'); input.focus(); }
    function userBubble(text, hadPhoto) { const m = h('div', { class: 'msg' }, h('div', { class: 'bubble me' }, h('span', { class: 'vh', text: 'You asked: ' }), text, hadPhoto ? ' (with a photo)' : '')); log.append(m); scrollEnd(m); }
    function setBusy(b) { S.busy = b; input.setAttribute('aria-busy', String(b)); sendBtn.toggleAttribute('aria-disabled', b); }
    function cancel() { if (S.ctrl) { S.ctrl.abort(); S.ctrl = null; } if (S.busy) { setBusy(false); const t = log.querySelector('.typing-msg'); if (t) t.remove(); say('Stopped.'); } }

    async function ask(text) {
      text = String(text || '').trim();
      if (S.busy) { hint('I am still working on the last question. Press Escape to cancel it.'); return; }
      const photo = S.image;
      if (!text && !photo) { hint('Type a question first, or choose an idea.'); input.focus(); return; }
      if (!text && photo) text = 'What does this photo show?';
      if (!S.guided) { hint('Still loading the data. Please wait a moment and try again.'); return; }
      hint('');
      const first = log.querySelector('.state, .msg.bot:only-child');
      if (first && S.answers === 0) log.textContent = '';
      S.lastQ = text; userBubble(text, !!photo);
      const thinking = h('div', { class: 'msg typing-msg' }, h('div', { class: 'typing', role: 'status' }, h('span', { class: 'dots', 'aria-hidden': 'true' }, h('i'), h('i'), h('i')), h('span', { text: 'Looking for places…' }),
        h('button', { type: 'button', class: 'btn btn-ghost', onclick: () => cancel() }, 'Cancel')));
      log.append(thinking); scrollEnd(thinking); say('Looking for places.'); setBusy(true);
      S.ctrl = new g.AbortController();
      const view = answerView(); let events = 0, useLocal = false;
      try {
        useLocal = !!(wantsModel() && S.health && S.health.model);
        const eng = useLocal ? S.local : S.guided;
        if (useLocal) S.local.fallback = S.guided;
        status(useLocal ? 'question sent to the model server (' + ((S.health.models || [])[0] || 'model') + ').' : 'question answered in Guided mode, no model called: ' + (!wantsModel() ? 'Settings is on Guided' : !S.health ? 'the model server has not answered yet' : 'the model server has no model') + '.');
        const gen = eng.ask(text, ctxNow(), { signal: S.ctrl.signal, image: photo ? photo.dataUrl.split(',')[1] : null, history: useLocal ? S.turns.slice(-6) : [] });
        for await (const ev of gen) { if (useLocal) { if (ev.type === 'note') status('model not used: ' + ev.message); if (ev.type === 'meta') status(ev.engine === 'model' ? 'model reply. Understanding the question: ' + ((ev.model_use || {}).plan || 'unknown') + '. Main sentence: ' + ((ev.model_use || {}).answer || 'unknown') + '.' : 'reply came from ' + (ev.engine || 'guided') + ' mode, not the model.'); } if (thinking.isConnected && ev.type !== 'note') thinking.remove(); events++; view.handle(ev); if (S.ctrl === null) break; }
      } catch (err) { events++; view.handle({ type: 'error', message: 'Something went wrong while looking that up.' }); }
      if (thinking.isConnected) thinking.remove();
      if (!events) view.handle({ type: 'error', message: 'I did not get an answer. Please try again.' });
      view.finish();
      if (!photo && view.said()) { S.turns.push({ role: 'user', text }, { role: 'assistant', text: view.said() }); S.turns = S.turns.slice(-12); }
      if (useLocal && S.health.hosted && !S.toldOnline) { S.toldOnline = true; const n = h('p', { class: 'hint small', text: 'Answers use an online model, so your messages are sent to it. Facts about places come only from the saved data. You can switch to Guided in Settings.' }); log.append(n); scrollEnd(n); }
      S.ctrl = null; setBusy(false); S.image = null; renderAttach();
    }

    // ---- one answer on screen: sentence, one place card, More, three follow-up chips ----
    function answerView() {
      const A = { main: '', kind: 'answer', parts: [], details: [], cards: [], actions: [], unknown: null, sources: [], meta: null, clarify: null, call: null, error: null, followups: [], done: null };
      let msg = null, bubble = null;
      const ensure = () => {
        if (msg) return;
        S.answers++;
        bubble = h('div', { class: 'bubble bot' });
        msg = h('div', { class: 'msg bot' }, h('h2', { class: 'vh', tabindex: '-1', id: 'ans' + S.answers, text: 'Answer' }), bubble);
        log.append(msg); scrollEnd(msg);
      };
      return {
        said() { const lead = A.cards[0]; return A.error ? '' : (A.parts.join(' ') + (lead && lead.name && A.parts.join(' ').indexOf(lead.name) < 0 ? ' (' + lead.name + ')' : '')).slice(0, 400); },
        handle(ev) {
          if (ev.type === 'note') { hint(ev.message); return; }
          ensure();
          if (ev.type === 'text') { A.main = ev.delta; A.kind = ev.kind; A.parts = ev.parts || [ev.delta]; bubble.textContent = A.parts.join(' '); }
          else if (ev.type === 'detail') A.details = ev.items;
          else if (ev.type === 'card') A.cards.push(ev.card);
          else if (ev.type === 'action') A.actions.push(ev);
          else if (ev.type === 'call') A.call = ev;
          else if (ev.type === 'unknown') A.unknown = ev;
          else if (ev.type === 'sources') A.sources = ev.items;
          else if (ev.type === 'clarify') A.clarify = ev;
          else if (ev.type === 'followups') A.followups = ev.items || [];
          else if (ev.type === 'meta') A.meta = ev;
          else if (ev.type === 'done') A.done = ev;
          else if (ev.type === 'error') { A.error = ev.message; A.kind = 'error'; if (bubble) { bubble.remove(); bubble = null; } }
        },
        finish() {
          ensure();
          if (A.error) { msg.replaceChildren(msg.firstChild, errorCard(A.error)); input.value = S.lastQ || ''; grow(); say(A.error); scrollEnd(msg); return; }
          if (A.clarify) {
            const row = h('div', { class: 'suggest', role: 'group', 'aria-label': 'Choose one' });
            for (const o of A.clarify.options || []) row.append(h('button', { type: 'button', class: 'chip', onclick: () => ask(o.message), text: o.label }));
            msg.append(row);
          }
          const lead = A.cards.find((c) => c.lead) || A.cards[0];
          { const rs = [...new Set(A.cards.map((c) => regionOf(c.place_id)).filter(Boolean))]; setCityLine(S.region && rs.length === 1 && rs[0] !== S.region ? rs[0] : null); }
          const conf = (A.meta && A.meta.confidence) || '';
          if (lead && !lead.event) msg.append(placeCard(lead));
          else if (lead && lead.event) msg.append(eventCard(lead));
          else if (conf) msg.append(h('p', { class: 'conf' }, ic('info'), h('span', { text: conf })));
          if (A.call && !(lead && lead.phone && String(lead.phone).replace(/\D/g, '') === String(A.call.phone).replace(/\D/g, ''))) msg.append(h('p', { class: 'conf' }, ic('ask'), h('span', {}, 'Call ' + A.call.name + ': ', h('a', { href: 'tel:' + String(A.call.phone).replace(/[^0-9+]/g, ''), text: A.call.phone }))));
          const more = A.kind === 'clarify' ? null : moreBlock(A, lead);
          if (more) msg.append(more.btn, more.box);
          if (A.followups.length) msg.append(h('div', { class: 'followups', role: 'group', 'aria-label': 'Ask next' }, A.followups.slice(0, 3).map((f) => h('button', { type: 'button', class: 'chip', onclick: () => ask(f.message), text: f.label }))));
          const sentence = A.parts.join(' ');
          say((A.kind === 'emergency' ? 'Emergency. ' : '') + sentence + (lead ? ' ' + lead.name + ', ' + (RK[lead.rating] ? WORD[RK[lead.rating]] : '') + '.' : ''));
          if (['unknown', 'no_data'].includes(A.kind) && A.main) logGap(S.lastQ, A.unknown && A.unknown.about);
          scrollToAnswer(msg);
        },
      };
    }
    function logGap(q, about) { const gaps = readJSON('openway.gaps', []); gaps.push({ q: String(q).slice(0, 200), about: (about || []).slice(0, 3), t: deviceToday() }); store.set('openway.gaps', JSON.stringify(gaps.slice(-50))); }
    function errorCard(message) {
      return h('div', { class: 'state error', role: 'alert' }, h('span', { class: 'big' }, ic('alert')), h('p', { class: 'lead', text: 'Could not answer' }), h('p', { class: 'muted', text: message + ' Your question is kept in the box.' }),
        h('div', { class: 'rowbtns' }, h('button', { type: 'button', class: 'btn btn-secondary', onclick: () => { input.value = S.lastQ || ''; grow(); ask(S.lastQ); } }, ic('route'), 'Try again'), reportBtn('Problem with an answer: "' + S.lastQ + '"')));
    }
    function confidenceOf(c) {
      if (c.confidence) return c.confidence;
      const s = (c.sources || [])[0];
      return s ? 'Source · ' + (s.label || 'listed source') + (s.date ? ', ' + (O.composer ? O.composer.monthYear(s.date) : s.date) : '') : 'Not known · no source in our data';
    }
    function actionsRow(c) {
      const row = h('div', { class: 'actions' });
      const hasPt = c.lat !== null && c.lat !== undefined;
      if (hasPt) row.append(h('a', { class: 'btn btn-primary', href: mapUrl(c.place_id), onclick: (e) => { const profile = (S.needs && (S.needs.mobility === 'cane' || (S.needs.rely || []).includes('screen_reader'))) ? 'blind' : 'wheelchair'; if (fire('atlas:route-to', { placeId: c.place_id, profile })) e.preventDefault(); } }, ic('route'), 'Route here'));
      if (hasPt || (S.guided && S.guided.kb.byId.get(c.place_id))) row.append(h('a', { class: 'btn btn-secondary', href: mapUrl(c.place_id), onclick: (e) => { if (fire('atlas:show-places', { ids: [c.place_id] })) e.preventDefault(); } }, ic('map'), 'Show on map'));
      if (c.rating === 'unknown' || !RK[c.rating] || c.rating === 'unknown') row.append(reportBtn('Report what I know about ' + c.name + '\n', 'Report what you know', c));
      if (c.phone) row.append(h('a', { class: 'btn btn-secondary', href: 'tel:' + c.phone.replace(/[^0-9+]/g, ''), 'aria-label': 'Call ' + c.name + ' at ' + c.phone }, ic('ask'), 'Call ' + c.phone));
      return row;
    }
    function placeCard(c) {
      const k = RK[c.rating] || 'unknown', f = (c.facts || [])[0];
      const id = 'pn' + S.answers;
      const dist = c.distance_text ? c.distance_text.replace(/^about /, '') : '';
      return h('article', { class: 'card place pb', 'aria-labelledby': id },
        h('div', { class: 'band ' + k }, ic(k), h('span', { text: WORD[k] }), dist ? h('span', { class: 'dist small', text: dist + (c.direction ? ' ' + c.direction : '') }) : null),
        h('div', { class: 'body' }, h('div', {}, h('h3', { class: 'name', id, text: c.name }), c.type ? h('p', { class: 'kind muted small', text: c.type }) : null),
          f ? h('ul', { class: 'facts' }, h('li', {}, ic(String(f.value) === 'no' ? 'no' : String(f.value) === 'yes' ? 'yes' : 'info'), h('span', {}, f.label, f.detail ? [h('br'), h('span', { class: 'muted small', text: f.detail })] : null), h('span', { class: 'v', text: String(f.value).replace(/^./, (x) => x.toUpperCase()) }))) : null,
          h('p', { class: 'conf' }, ic(/^Confirmed/.test(confidenceOf(c)) ? 'check' : /^Not known/.test(confidenceOf(c)) ? 'unknown' : 'clock'), h('span', { text: confidenceOf(c) })),
          c.note ? h('p', { class: 'muted small', text: c.note }) : null, actionsRow(c)));
    }
    function eventCard(c) {
      const e = c.event, id = 'pn' + S.answers;
      return h('article', { class: 'card place pb', 'aria-labelledby': id },
        h('div', { class: 'band unknown' }, ic('clock'), h('span', { text: e.when_text })),
        h('div', { class: 'body' }, h('div', {}, h('h3', { class: 'name', id, text: e.title }), h('p', { class: 'kind muted small', text: c.name })),
          h('p', { class: 'conf' }, ic('info'), h('span', { text: e.access && e.access.length ? 'Access: ' + e.access.join(', ') : 'No access details in my data. Check with the venue.' })),
          h('div', { class: 'actions' }, /^https?:/.test(e.url || '') ? h('a', { class: 'btn btn-secondary', href: e.url, target: '_blank', rel: 'noopener noreferrer' }, ic('list'), 'Event page', h('span', { class: 'vh', text: ' (new tab)' })) : null, actionsRow(c).childNodes.length ? actionsRow(c) : null)));
    }
    function moreBlock(A, lead) {
      const others = A.cards.filter((c) => c !== lead);
      const known = lead && !lead.event ? (lead.facts || []).slice(1) : [];
      const sections = [];
      let n = 0;
      const sec = (title, ...kids) => { n++; const id = 'mo' + S.answers + '-' + n; return h('section', { 'aria-labelledby': id }, h('h3', { id, text: title }), ...kids); };
      if (others.length) sections.push(sec('Other places', others.map((c) => h('div', { class: 'list-item' }, h('div', { class: 'row1' }, h('span', { class: 't', text: c.event ? c.event.title : c.name }), c.distance_text ? h('span', { class: 'small muted', text: c.distance_text.replace(/^about /, '') }) : null), c.event ? h('p', { text: c.event.when_text + ' · ' + c.name }) : badge(c.rating), c.note ? h('p', { text: c.note }) : ((c.facts || [])[0] ? h('p', { text: (c.facts[0].detail || c.facts[0].label) }) : null)))));
      if (known.length) sections.push(sec('Also known', h('ul', { class: 'facts' }, known.map((f) => h('li', {}, ic(String(f.value) === 'no' ? 'no' : 'yes'), h('span', {}, f.label, f.detail ? [h('br'), h('span', { class: 'muted small', text: f.detail })] : null), h('span', { class: 'v', text: String(f.value).replace(/^./, (x) => x.toUpperCase()) }))))));
      const unk = (A.unknown && A.unknown.about) || [];
      if (unk.length || A.details.length) sections.push(sec(unk.length ? 'Not known' : 'More detail', h('ul', { class: 'plain' }, [...unk.map((t) => h('li', {}, ic('unknown'), t)), ...A.details.map((t) => h('li', {}, ic('info'), t))])));
      if (A.sources.length) sections.push(sec('Sources', A.sources.map((s) => h('div', { class: 'list-item' }, h('div', { class: 'row1' }, h('span', { class: 't', text: s.label || 'Source' })),
        h('p', {}, /^https?:/.test(s.url) ? h('a', { href: s.url, target: '_blank', rel: 'noopener noreferrer' }, String(s.url).replace(/^https?:\/\/(www\.)?/, '').slice(0, 60), h('span', { class: 'vh', text: ' (opens in a new tab)' })) : '', ' · ' + (s.date ? (O.composer ? O.composer.monthYear(s.date) : s.date) : 'no date given')), s.quote ? h('blockquote', { class: 'q', text: '“' + s.quote + '”' }) : null))));
      if (A.meta && A.meta.as_of) sections.push(h('p', { class: 'muted small', text: 'Data snapshot: ' + (O.composer ? O.composer.fullDate(A.meta.as_of) : A.meta.as_of) + '. It can be out of date, so call ahead for anything important.' }));
      if (A.done && A.done.removed) sections.push(h('p', { class: 'muted small', text: 'I removed ' + A.done.removed + ' sentence' + (A.done.removed > 1 ? 's' : '') + ' I could not check against a source.' }));
      const rep = A.actions.find((a) => a.action === 'report');
      const tools = h('div', { class: 'tools' }, h('button', { type: 'button', class: 'btn btn-secondary', 'aria-pressed': 'false', onclick: (e) => readAloud(A, e.currentTarget) }, ic('volume'), h('span', { text: 'Read aloud' })), reportBtn(rep ? rep.text : 'Problem with an answer: "' + S.lastQ + '"\n'));
      const ids = [].concat(...A.actions.filter((a) => a.action === 'show_on_map').map((a) => a.ids));
      if (ids.length > 1) tools.prepend(h('a', { class: 'btn btn-secondary', href: mapUrl(ids[0]), onclick: (e) => { if (fire('atlas:show-places', { ids })) e.preventDefault(); } }, ic('map'), 'Show all on map'));
      const box = h('div', { class: 'more', id: 'm' + S.answers, hidden: true }, ...sections, tools);
      const btn = h('button', { type: 'button', class: 'btn btn-ghost more-btn', 'aria-expanded': 'false', 'aria-controls': box.id }, h('span', { text: 'More' }), ic('down'));
      btn.addEventListener('click', () => { const open = box.hidden; box.hidden = !open; btn.setAttribute('aria-expanded', String(open)); btn.firstChild.textContent = open ? 'Less' : 'More'; btn.lastChild.classList.toggle('flip', open); });
      return { btn, box };
    }
    function reportBtn(text, label, card) {
      return h('button', { type: 'button', class: 'btn btn-secondary', onclick: () => {
        const detail = { text }; if (card) { detail.placeId = card.place_id; detail.region = regionOf(card.place_id); }
        ui_emit(detail);
      } }, ic('report'), label || 'Report a problem');
    }
    const ui_emit = (detail) => g.atlas.emit('atlas:open-report', detail) > 0;

    // ---- read aloud ----
    function spoken(A) {
      const parts = [A.parts.join(' ')];
      const lead = A.cards.find((c) => c.lead) || A.cards[0];
      if (lead && !lead.event) parts.push(lead.name + (lead.distance_text ? ', ' + lead.distance_text + ' ' + (lead.direction || '') : '') + '. ' + (lead.facts || []).slice(0, 2).map((f) => f.label + ': ' + f.value).join('. ') + '.');
      if (A.unknown && A.unknown.about && A.unknown.about.length) parts.push('I do not know: ' + A.unknown.about.join(', ') + '.');
      return parts.join(' ');
    }
    function readAloud(A, btn) {
      const V = O.voice;
      if (!V.supportsOut()) { hint('Reading aloud is not available in this browser. Your screen reader can read the answer.'); say('Reading aloud is not available in this browser.'); return; }
      if (S.speaking === btn) { V.stop(); S.speaking = null; btn.setAttribute('aria-pressed', 'false'); btn.querySelector('span').textContent = 'Read aloud'; return; }
      S.speaking = btn; btn.setAttribute('aria-pressed', 'true'); btn.querySelector('span').textContent = 'Stop reading';
      V.speak(spoken(A), { rate: parseFloat(S.prefs.rate), onend: () => { if (S.speaking === btn) { S.speaking = null; btn.setAttribute('aria-pressed', 'false'); btn.querySelector('span').textContent = 'Read aloud'; } } });
    }

    // ---- voice in: idle, recording, 10 seconds left, restarting, processing, transcript, limit, denied ----
    const speech = O.speech.create(Object.assign({}, g.__OPENWAY_SPEECH || {}, {
      onState: (state, info) => { if (state === S.voice) updateVoiceTick(info); else setVoice(state, info); },
      onText: (t) => { input.value = t; grow(); if (S.voice === 'recording' || S.voice === 'warning' || S.voice === 'restarting') input.scrollTop = input.scrollHeight; },
    }));
    const voiceMsg = {
      recording: ['Listening', 'Pauses are fine. The box is read-only while listening.', 'rec'],
      warning: ['Listening · 10 seconds left', 'Still recording. Say the last part, or tap Stop.', 'warn'],
      restarting: ['Listening again…', 'The browser paused after a gap. Your words so far are kept.', 'warn'],
      processing: ['Adding your last words…', 'Stopping…', 'rec'],
    };
    function setVoice(state, info) {
      const had = voiceHost.contains(doc.activeElement);
      S.voice = state; S.voiceInfo = info || {};
      const live_ = ['recording', 'warning', 'restarting', 'processing'].includes(state);
      input.readOnly = live_; if (live_) input.setAttribute('aria-readonly', 'true'); else input.removeAttribute('aria-readonly');
      if (live_ || state === 'denied' || state === 'unsupported') micBtn.setAttribute('aria-disabled', 'true'); else micBtn.removeAttribute('aria-disabled');
      micBtn.setAttribute('aria-pressed', String(live_));
      micBtn.setAttribute('aria-label', live_ ? 'Speak, listening now' : (state === 'denied' || state === 'unsupported') ? 'Speak, not available' : 'Speak');
      voiceHost.textContent = '';
      const words = (info && info.words) || 0;
      if (voiceMsg[state]) {
        const [title, text, cls] = voiceMsg[state];
        voiceHost.append(h('section', { class: 'voicebar ' + cls, 'aria-label': 'Voice input' }, h('div', { class: 'vrow' }, h('span', { class: 'vstate' }, state === 'processing' ? ic('spinner', 'spin') : h('span', { class: 'rdot', 'aria-hidden': 'true' }), title), h('span', { class: 'counter', 'aria-hidden': 'true', id: 'vcount' })),
          h('div', { class: 'vprog', 'aria-hidden': 'true' }, h('i', { id: 'vbar' })), h('p', { text }), h('div', { class: 'vbtns' }, state === 'processing' ? null : h('button', { type: 'button', class: 'btn btn-secondary', 'data-vstop': true, onclick: () => speech.stop() }, ic('stop'), 'Stop'))));
        updateVoiceTick(info);
        if (had || state === 'recording') { const b = voiceHost.querySelector('[data-vstop]'); if (b) b.focus(); }
      } else if (state === 'transcript' || state === 'limit') {
        const lim = state === 'limit';
        voiceHost.append(h('section', { class: 'voicebar ok', 'aria-label': 'Voice input' }, h('div', { class: 'vrow' }, h('span', { class: 'vstate' }, ic(lim ? 'clock' : 'check'), lim ? (info.max || 60) + '-second limit reached' : 'Stopped'), lim ? h('span', { class: 'counter', 'aria-hidden': 'true', text: fmtClock(info.max || 60) + ' of ' + fmtClock(info.max || 60) }) : null),
          h('p', { text: lim ? 'Everything you said (' + words + ' word' + (words === 1 ? '' : 's') + ') is in the box. Edit it, press Send, or add more.' : words + ' word' + (words === 1 ? ' is' : 's are') + ' in the box. Check them, then press Send. Nothing is sent yet.' }),
          h('div', { class: 'vbtns' }, h('button', { type: 'button', class: 'btn btn-secondary', 'data-vmore': true, onclick: () => { speech.start(input.value); } }, ic('mic'), 'Add more'), lim ? null : h('button', { type: 'button', class: 'btn btn-secondary', onclick: () => { speech.clear(); input.focus(); } }, ic('trash'), 'Clear'))));
        if (had) { const b = voiceHost.querySelector('[data-vmore]'); if (b) b.focus(); } else if (state === 'transcript') input.focus();
      } else if (state === 'denied' || state === 'unsupported') {
        voiceHost.append(h('section', { class: 'voicebar bad', 'aria-label': 'Voice input' }, h('div', { class: 'vrow' }, h('span', { class: 'vstate' }, ic(state === 'denied' ? 'no' : 'offline'), state === 'denied' ? 'Microphone is blocked' : 'Voice input is not available')),
          h('p', { text: state === 'denied' ? 'Allow the microphone for this site in your browser settings, then tap the microphone again.' : 'This browser cannot turn speech into text. You can type your question, or use the dictation key on your keyboard or phone.' }),
          h('div', { class: 'vbtns' }, h('button', { type: 'button', class: 'btn btn-secondary', onclick: () => { setVoice('idle'); input.focus(); } }, ic('close'), 'Type instead'))));
        if (had) voiceHost.querySelector('button').focus();
      }
      const say_ = { recording: 'Listening.', warning: '10 seconds left.', restarting: 'Listening again. Your words so far are kept.', processing: 'Adding your last words.', transcript: 'Stopped. ' + words + ' word' + (words === 1 ? ' is' : 's are') + ' in the box.', limit: (info && info.max || 60) + '-second limit reached. ' + words + ' words are in the box.', denied: 'Microphone is blocked.', unsupported: 'Voice input is not available in this browser.' }[state];
      if (say_) say(say_);
      hintEl.hidden = state !== 'idle' || !hintEl.textContent;
      layout();
    }
    function updateVoiceTick(info) {
      const c = $('#vcount'), b = $('#vbar'); if (!c || !info) return;
      c.textContent = fmtClock(info.seconds || 0) + ' of ' + fmtClock(info.max || 60);
      b.style.width = Math.min(100, ((info.seconds || 0) / (info.max || 60)) * 100) + '%';
    }
    const VOICE_HINT = 'Tap the microphone to speak. Up to 60 seconds. Nothing is sent until you press Send. Your browser may send your voice to its maker to turn it into text.';
    micBtn.setAttribute('aria-describedby', 'ch-hint');
    micBtn.addEventListener('focus', () => { if (S.voice === 'idle') { hintEl.textContent = VOICE_HINT; hintEl.hidden = false; } });
    micBtn.addEventListener('click', () => {
      if (['recording', 'warning', 'restarting', 'processing'].includes(S.voice)) { speech.stop(); return; }
      if (S.voice === 'denied') return;
      if (!speech.supported()) { setVoice('unsupported'); return; }
      hintEl.textContent = VOICE_HINT;
      speech.start(input.value);
    });

    // ---- photo (needs the local model) ----
    const localReady = () => wantsModel() && S.health && S.health.model;
    photoBtn.addEventListener('click', () => {
      if (S.health && S.health.hosted) { const m = 'Photo questions do not work with the online model yet. Please ask in words.'; hint(m); say(m); return; }
      if (!localReady()) { const m = 'Photo questions need the local model. Open Settings and choose Local model, or ask in words.'; hint(m); say(m); return; }
      fileInput.click();
    });
    fileInput.addEventListener('change', async () => {
      const f = fileInput.files && fileInput.files[0]; fileInput.value = '';
      if (!f) return;
      try { S.image = await O.photo.shrink(f); renderAttach(); hint('Photo ready. It is shrunk on this device and its location data is removed. Type your question, then press Send.'); input.focus(); }
      catch (e) { hint(e.message); say(e.message); }
    });
    function renderAttach() {
      const host = $('#ch-attach'); host.textContent = '';
      if (!S.image) { host.hidden = true; return; }
      host.hidden = false;
      host.append(h('img', { src: S.image.dataUrl, alt: 'Your photo, shown small. It is not saved.' }), h('span', { text: 'Photo attached (not saved).' }), h('button', { type: 'button', class: 'btn btn-secondary', onclick: () => { S.image = null; renderAttach(); input.focus(); } }, ic('trash'), 'Remove'));
    }

    // ---- sending, keyboard ----
    form.addEventListener('submit', (e) => { e.preventDefault(); if (['recording', 'warning', 'restarting', 'processing'].includes(S.voice)) return; const q = input.value; if (!q.trim() && !S.image) { hint('Type a question first, or choose an idea.'); input.focus(); return; } input.value = ''; grow(); speech.reset(); setVoice('idle'); ask(q); });
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); } });
    root.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape' || doc.querySelector('.sheet.modal')) return;
      if (S.busy) { cancel(); return; }
      if (!settingsEl.hidden) { toggleSettings(false); settingsBtn.focus(); e.stopPropagation(); return; }
      if (O.voice.supportsOut() && S.speaking) { O.voice.stop(); }
    });
    g.addEventListener('pagehide', () => { O.voice.stop(); speech.reset(); });
    doc.addEventListener('visibilitychange', () => { if (doc.hidden && ['recording', 'warning', 'restarting'].includes(S.voice)) speech.stop(); });

    // ---- boot ----
    const api = { ask, root, state: S, speech, focus() { input.focus(); } };
    greeting(); refreshMode(); hint('Loading the data…'); sendBtn.setAttribute('aria-disabled', 'true');
    const get = async (u) => { const r = await fetch(u); if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); };
    (async () => {
      try {
        const inl = g.__OPENWAY_DATA;
        const [r, cinc, ox] = inl ? [inl.rules, inl.cincinnati, inl.oxford] : await Promise.all([get(base + 'rules.json'), get(base + 'cincinnati.json'), get(base + 'oxford.json')]);
        S.guided = new O.engine.GuidedEngine([cinc, ox], r);
        if (g.AtlasReport) g.AtlasReport.setPlaces(S.guided.kb.places.filter((p) => p.layer !== 'event').map((p) => ({ id: p.link_id, name: p.name, region: p.region, rating: RK[p.rating] || 'unknown', layer: LAYER_NAME[p.layer] || 'Place', pt: p.lat == null ? null : [p.lat, p.lon] })));
        hint(''); sendBtn.removeAttribute('aria-disabled'); root.dispatchEvent(new g.CustomEvent('ow:ready'));
        checkHealth();
      } catch (e) {
        hint('');
        log.textContent = '';
        log.append(h('div', { class: 'state error', role: 'alert' }, h('span', { class: 'big' }, ic('alert')), h('p', { class: 'lead', text: 'Could not load the data' }), h('p', { class: 'muted', text: 'I could not load the data I answer from. Check your connection, then reload this page. The map still works.' })));
      }
    })();
    return api;
  }
  O.chat = { mount };
})(typeof globalThis !== 'undefined' ? globalThis : this);
