/* Openway Assistant: the chat interface (plain JavaScript, no build step).
   Openway.chat.mount(container, options) builds the whole interface: header, settings, conversation with answer cards,
   quick-ask tiles, "My needs", voice, photo, and the hooks to the map (window events atlas:show-places, atlas:route-to,
   atlas:open-report). Everything is real text and landmarks; focus stays where the user left it. */
(function (g) {
  'use strict';
  const O = (g.Openway = g.Openway || {});
  const doc = g.document;

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
  const icon = path => { const s = doc.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('class', 'ow-i'); s.setAttribute('viewBox', '0 0 20 20'); s.setAttribute('aria-hidden', 'true'); s.setAttribute('focusable', 'false'); s.innerHTML = path; return s; };
  const ICONS = {
    mic: '<path d="M10 2.5a2.5 2.5 0 0 0-2.5 2.5v4a2.5 2.5 0 0 0 5 0V5A2.5 2.5 0 0 0 10 2.5zM5 9a5 5 0 0 0 10 0M10 14v3" stroke="currentColor" stroke-width="1.7" fill="none" stroke-linecap="round"/>',
    cam: '<path d="M3 6.5h3l1.2-2h5.6l1.2 2h3V16H3z" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linejoin="round"/><circle cx="10" cy="11" r="3" stroke="currentColor" stroke-width="1.6" fill="none"/>',
    gear: '<circle cx="10" cy="10" r="2.6" stroke="currentColor" stroke-width="1.6" fill="none"/><path d="M10 2.5v2M10 15.5v2M2.5 10h2M15.5 10h2M4.7 4.7l1.4 1.4M13.9 13.9l1.4 1.4M4.7 15.3l1.4-1.4M13.9 6.1l1.4-1.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    send: '<path d="M3 10l14-6-5 13-2.5-5.5z" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linejoin="round"/>',
    speaker: '<path d="M3.5 8v4h3l4 3V5l-4 3zM13.5 7.5a3.5 3.5 0 0 1 0 5M15.5 5.5a6.5 6.5 0 0 1 0 9" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    x: '<path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  };

  const store = {
    mem: {}, ok: null,
    get(k) { try { const v = g.localStorage.getItem(k); this.ok = true; return v; } catch (e) { this.ok = false; return this.mem[k] === undefined ? null : this.mem[k]; } },
    set(k, v) { this.mem[k] = v; try { g.localStorage.setItem(k, v); this.ok = true; } catch (e) { this.ok = false; } },
    del(k) { delete this.mem[k]; try { g.localStorage.removeItem(k); } catch (e) { /* blocked */ } },
  };
  const readJSON = (k, d) => { try { const v = store.get(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } };

  function deviceToday() {
    const q = new URLSearchParams(g.location.search).get('today');
    if (g.__OPENWAY_TODAY) return g.__OPENWAY_TODAY;
    if (q && /^\d{4}-\d{2}-\d{2}$/.test(q)) return q;
    const d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  const SIZES = [['1', 'Normal'], ['1.25', 'Large'], ['1.5', 'Extra large']];
  const MOBILITY = [['manual', 'Manual wheelchair'], ['power', 'Power chair'], ['cane', 'Cane or guide'], ['other', 'Something else'], ['', 'Prefer not to say']];
  const STEPS = [['cannot', 'No, I cannot use steps'], ['some', 'A few steps are fine'], ['', 'Not sure']];
  const RELY = [['screen_reader', 'A screen reader'], ['large_text', 'Large text'], ['voice', 'Speaking and listening']];
  const RATE_GLYPH = { accessible: '✓', partial: '~', not_accessible: '✕', unknown: '?' };

  function mount(container, options) {
    options = options || {};
    const mode = options.mode || 'page';
    const base = options.base === undefined ? 'assistant/' : options.base;
    const S = {
      prefs: Object.assign({ size: '1', plain: false, engine: 'guided', rate: '1' }, readJSON('openway.prefs', {})),
      needs: readJSON('openway.needs', {}), location: null, busy: false, ctrl: null, guided: null, local: null, health: null,
      image: null, listening: null, lastQ: null, speaking: false, opener: options.opener || null, answers: 0,
    };
    const uid = 'ow' + Math.random().toString(36).slice(2, 7);
    const id = n => (n === 'q' && options.inputId) ? options.inputId : uid + '-' + n;
    const HL = mode === 'page' ? 'h2' : 'h3', CH = mode === 'page' ? 'h3' : 'h4';   // heading levels step down one at a time
    const root = container;
    root.classList.add('ow', mode === 'panel' ? 'ow-panel' : 'ow-page');
    root.textContent = '';
    if (mode === 'panel') { root.setAttribute('role', 'dialog'); root.setAttribute('aria-modal', 'false'); root.setAttribute('aria-labelledby', id('title')); }
    const applySize = () => { root.style.setProperty('--ow-scale', S.prefs.size); root.toggleAttribute('data-big', parseFloat(S.prefs.size) >= 1.25); };
    applySize();
    const savePrefs = () => store.set('openway.prefs', JSON.stringify(S.prefs));

    // ---- skeleton ----
    const modeLabel = h('span', { id: id('mode') });
    const settingsBtn = h('button', { type: 'button', 'aria-expanded': 'false', 'aria-controls': id('settings'), onclick: () => toggleSettings() }, icon(ICONS.gear), 'Settings');
    const closeBtn = mode === 'panel' ? h('button', { type: 'button', class: 'ow-ghost', 'aria-label': 'Close the assistant', onclick: () => api.close() }, icon(ICONS.x), 'Close') : null;
    const head = h('div', { class: 'ow-head' },
      h('div', { class: 'ow-titles' }, h(mode === 'page' ? 'h1' : 'h2', { id: id('title'), text: 'Openway Assistant' }),
        h('p', { class: 'ow-sub' }, modeLabel, ' \u00b7 Cincinnati and Oxford')),
      settingsBtn, closeBtn);
    const settings = h('section', { class: 'ow-settings', id: id('settings'), hidden: true, 'aria-label': 'Settings' });
    const log = h('div', { class: 'ow-log', id: id('log'), role: 'log', 'aria-live': 'off', 'aria-label': 'Conversation', tabindex: '0' });
    const announcer = h('div', { class: 'ow-vh', role: 'status', 'aria-live': 'polite', 'aria-atomic': 'true', id: id('announce') });
    const status = h('p', { class: 'ow-status', id: id('status'), role: 'status', 'aria-live': 'polite' });
    const input = h('input', { type: 'text', id: id('q'), autocomplete: 'off', enterkeyhint: 'send', placeholder: 'Ask about a restroom, parking, food, events…', 'aria-describedby': id('status') });
    const sendBtn = h('button', { type: 'submit', class: 'ow-primary' }, icon(ICONS.send), 'Send');
    const stopBtn = h('button', { type: 'button', hidden: true, onclick: () => cancel() }, icon(ICONS.x), 'Stop');
    const micBtn = h('button', { type: 'button', 'aria-pressed': 'false', onclick: () => toggleListen() }, icon(ICONS.mic), 'Speak');
    const camBtn = h('button', { type: 'button', onclick: () => pickPhoto() }, icon(ICONS.cam), 'Photo');
    const fileInput = h('input', { type: 'file', accept: 'image/*', class: 'ow-vh', tabindex: '-1', 'aria-hidden': 'true', onchange: () => onPhoto() });
    const attach = h('div', { class: 'ow-attach', hidden: true });
    const miniTiles = h('ul', { class: 'ow-tiles-mini', 'aria-label': 'Quick questions', hidden: true });
    const form = h('form', { 'aria-label': 'Ask a question', onsubmit: e => { e.preventDefault(); const q = input.value; input.value = ''; ask(q); } },
      h('label', { class: 'ow-vh', for: id('q') }, 'Your question'), input, sendBtn);
    const compose = h('div', { class: 'ow-compose' }, miniTiles, form, h('div', { class: 'ow-tools' }, micBtn, camBtn, stopBtn), attach, status, fileInput);
    const needsDlg = h('dialog', { 'aria-labelledby': id('needs-h') });
    const nav = mode === 'page' ? h('nav', { class: 'ow-topnav', 'aria-label': 'Maps' }, 'Open the map:', h('a', { href: (g.__OPENWAY_DATA ? g.__OPENWAY_DATA.cincinnati.site + '/' : '') + 'cincinnati.html', text: 'Cincinnati' }), h('a', { href: (g.__OPENWAY_DATA ? g.__OPENWAY_DATA.oxford.site + '/' : '') + 'oxford.html', text: 'Oxford' })) : null;
    const inner = h('div', { class: 'ow-inner' }, nav, head, settings, log, compose);
    if (mode === 'page') {
      root.append(inner, announcer, needsDlg);
    } else root.append(head, settings, log, compose, announcer, needsDlg);

    // ---- helpers ----
    const say = text => { announcer.textContent = ''; g.setTimeout(() => { announcer.textContent = text; }, 40); };
    const hint = text => { status.textContent = text || ''; };
    const rules = () => O.rules;
    const tiles = () => (rules() && rules().HELP_TILES) || [
      { label: 'Restroom near me', message: 'Where is the closest accessible restroom?' }, { label: 'Accessible parking', message: 'Where is accessible parking near me?' },
      { label: 'Food with no steps', message: 'Find food with no steps at the door' }, { label: 'Step-free route', message: 'How do I get to the Cincinnati Art Museum without steps?' },
      { label: 'Events this week', message: 'What events are on this week?' }, { label: 'Trails', message: 'What paved trails are there?' }];
    const regionOf = pid => { const p = S.guided && S.guided.kb.byId.get(pid); return p ? p.region : (options.region || 'cincinnati'); };
    const siteBase = () => (g.__OPENWAY_DATA && S.guided ? S.guided.kb.site + '/' : '');
    const mapUrl = pid => siteBase() + regionOf(pid) + '.html#place=' + encodeURIComponent(pid);
    const fire = (name, detail) => !g.dispatchEvent(new g.CustomEvent(name, { detail, cancelable: true }));
    const fullDate = iso => (O.composer && iso ? O.composer.fullDate(iso) : iso || '');
    const ctxNow = () => {
      const n = S.needs || {};
      const needs = {};
      if (n.mobility) needs.mobility = n.mobility;
      if (n.steps) needs.steps = n.steps;
      if (n.rely && n.rely.length) needs.rely = n.rely.slice();
      return { today: deviceToday(), region: options.region || null, location: S.location, needs, plain: !!S.prefs.plain };
    };
    const scrollEnd = el => { try { el.scrollIntoView({ block: 'nearest', behavior: 'auto' }); } catch (e) { /* old browser */ } };

    // ---- settings ----
    function radioGroup(name, legend, items, current, onchange, disabledMap) {
      const fs = h('fieldset', {}, h('legend', { text: legend }));
      const seg = h('div', { class: 'ow-seg' });
      for (const [val, label] of items) {
        const inp = h('input', { type: 'radio', name: id(name), value: val, checked: String(current) === String(val), disabled: disabledMap && disabledMap[val], onchange: () => onchange(val) });
        seg.append(h('label', {}, inp, h('span', { text: label })));
      }
      fs.append(seg);
      return fs;
    }
    function buildSettings() {
      settings.textContent = '';
      const localOk = !!(S.health && S.health.model);
      const engineFs = radioGroup('engine', 'How I answer', [['guided', 'Guided (no model)'], ['local', 'Local model']], S.prefs.engine, v => { S.prefs.engine = v; savePrefs(); refreshMode(); buildSettings(); },
        { local: !(S.health && S.health.reachable) });
      const eh = !S.health ? 'Checking for a local model…' : !S.health.reachable ? 'The local model is not available here. Guided mode answers from the saved data on this device and sends nothing anywhere.'
        : !S.health.model ? 'The local server is running, but no model is loaded. Start Ollama to use it. Guided mode still works.' : 'The local model runs on this computer. Answers are still checked against the data.';
      engineFs.append(h('p', { class: 'ow-hint', text: eh }));
      const sizeFs = radioGroup('size', 'Text size', SIZES, S.prefs.size, v => { S.prefs.size = v; applySize(); savePrefs(); });
      const plain = h('label', { class: 'ow-switch' }, h('input', { type: 'checkbox', role: 'switch', checked: !!S.prefs.plain, onchange: e => { S.prefs.plain = e.target.checked; savePrefs(); hint(S.prefs.plain ? 'Plain language is on: shorter sentences.' : 'Plain language is off.'); } }), h('span', { text: 'Plain language (shorter sentences)' }));
      const loc = h('label', { class: 'ow-switch' }, h('input', { type: 'checkbox', checked: !!S.location, onchange: e => { if (e.target.checked) useLocation(); else { S.location = null; hint('Location is off.'); } } }), h('span', { text: 'Use my location to sort by distance' }));
      const gaps = readJSON('openway.gaps', []);
      const gapRow = h('div', { class: 'ow-row' },
        h('button', { type: 'button', onclick: () => openNeeds() }, 'My needs'),
        h('button', { type: 'button', onclick: () => { toggleSettings(false); ask('What can you do?'); } }, 'What can I ask?'),
        h('button', { type: 'button', onclick: () => clearChat() }, 'Clear conversation'));
      const gapNote = h('p', { class: 'ow-hint' }, 'Nothing you type is sent anywhere in Guided mode. ',
        gaps.length ? [gaps.length + ' question' + (gaps.length > 1 ? 's' : '') + ' I could not answer ' + (gaps.length > 1 ? 'are' : 'is') + ' saved on this device only. ', h('button', { type: 'button', class: 'ow-ghost', onclick: () => { store.del('openway.gaps'); buildSettings(); } }, 'Clear them')] : '');
      settings.append(engineFs, sizeFs, plain, loc, gapRow, gapNote);
    }
    function toggleSettings(force) {
      const open = force === undefined ? settings.hidden : force;
      settings.hidden = !open; settingsBtn.setAttribute('aria-expanded', String(open));
      if (open) { buildSettings(); checkHealth(); }
    }
    function refreshMode() {
      const local = S.prefs.engine === 'local' && S.health && S.health.model;
      modeLabel.textContent = local ? 'Local model' : 'Guided mode (no model)';
      photoHint();
    }
    async function checkHealth() {
      if (!S.local) S.local = new O.engine.LocalEngine(options.serverBase || '', null);
      const info = await S.local.info();
      S.health = { reachable: !info.error, model: !!info.model, models: info.models || [] };
      refreshMode(); if (!settings.hidden) buildSettings();
    }
    function photoHint() { camBtn.title = S.prefs.engine === 'local' && S.health && S.health.model ? 'Ask about a photo' : 'Photo questions need the local model'; }

    // ---- My needs ----
    function openNeeds() {
      const n = S.needs || {};
      needsDlg.textContent = '';
      const group = (name, legend, items, cur) => h('fieldset', {}, h('legend', { text: legend }), ...items.map(([v, l]) => h('label', { class: 'ow-opt' }, h('input', { type: 'radio', name: id('n-' + name), value: v, checked: String(cur || '') === String(v) }), l)));
      const rely = h('fieldset', {}, h('legend', { text: '3. What do you rely on?' }), ...RELY.map(([v, l]) => h('label', { class: 'ow-opt' }, h('input', { type: 'checkbox', name: id('n-rely'), value: v, checked: (n.rely || []).includes(v) }), l)));
      const fm = h('form', { method: 'dialog' },
        h('h2', { id: id('needs-h'), text: 'My needs' }),
        h('p', { class: 'ow-hint', text: 'Three optional questions. They change which places I suggest. Your answers stay on this device only.' }),
        group('mobility', '1. How do you get around?', MOBILITY, n.mobility),
        group('steps', '2. Can you use steps?', STEPS, n.steps), rely,
        h('p', { class: 'ow-hint', id: id('needs-store') }),
        h('div', { class: 'ow-row' },
          h('button', { type: 'button', onclick: () => { clearNeeds(); } }, 'Clear my answers'),
          h('button', { type: 'button', onclick: () => needsDlg.close() }, 'Skip'),
          h('button', { type: 'submit', class: 'ow-primary', value: 'save' }, 'Save')));
      fm.addEventListener('submit', e => { e.preventDefault(); saveNeeds(fm); });
      needsDlg.append(fm);
      if (needsDlg.showModal) needsDlg.showModal(); else needsDlg.setAttribute('open', '');
      const first = fm.querySelector('input'); if (first) first.focus();
    }
    function saveNeeds(fm) {
      const val = nm => { const el = fm.querySelector('input[name="' + id('n-' + nm) + '"]:checked'); return el ? el.value : ''; };
      const rely = Array.from(fm.querySelectorAll('input[name="' + id('n-rely') + '"]:checked')).map(e => e.value);
      S.needs = { mobility: val('mobility'), steps: val('steps'), rely };
      store.set('openway.needs', JSON.stringify(S.needs));
      if (rely.includes('large_text') && S.prefs.size === '1') { S.prefs.size = '1.25'; applySize(); savePrefs(); }
      const note = store.ok === false ? 'Saved for this visit only: this browser blocks saving.' : 'Saved on this device.';
      hint('My needs: ' + note); say('My needs ' + note.toLowerCase());
      needsDlg.close(); if (!settings.hidden) buildSettings();
    }
    function clearNeeds() { S.needs = {}; store.del('openway.needs'); hint('My needs cleared.'); say('My needs cleared.'); needsDlg.close(); }
    needsDlg.addEventListener('close', () => { settingsBtn.focus(); });
    needsDlg.addEventListener('close', () => { if (settings.hidden) input.focus(); });

    // ---- location ----
    function useLocation(then) {
      if (!g.navigator.geolocation) { hint('Your browser cannot share your location. Tell me an area instead, such as downtown or uptown Oxford.'); say('Location is not available in this browser.'); return; }
      hint('Asking your browser for your location…');
      g.navigator.geolocation.getCurrentPosition(p => { S.location = [Math.round(p.coords.latitude * 1e4) / 1e4, Math.round(p.coords.longitude * 1e4) / 1e4]; hint('Location is on. I use it only on this device to sort by distance.'); if (then) then(); },
        () => { S.location = null; hint('I could not get your location. You can tell me an area instead, such as downtown or uptown Oxford.'); say('I could not get your location.'); }, { timeout: 10000, maximumAge: 60000 });
    }

    // ---- conversation ----
    function welcome() {
      log.textContent = '';
      const list = h('ul', { class: 'ow-tiles', 'aria-label': 'Quick questions' });
      const TI = ['<path d="M10 3a2 2 0 1 0 0 .01M7 8h6l-1 4h-4zM8 12l-1 5M12 12l1 5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>','<path d="M6 17V3h5a3.5 3.5 0 0 1 0 7H6" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round"/>','<path d="M6 3v6a2 2 0 0 0 2 2v6M8 3v5M4 3v5a2 2 0 0 0 2 2M14 17V3c-2 1.500-2.500 4-2.500 7H14" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>','<path d="M4 16c3-1 3-5 6-6s3-4 6-6M14 3h2v2" stroke="currentColor" stroke-width="1.7" fill="none" stroke-linecap="round"/>','<rect x="3.500" y="4.500" width="13" height="12" rx="2" stroke="currentColor" stroke-width="1.6" fill="none"/><path d="M3.500 8.500h13M7 3v3M13 3v3" stroke="currentColor" stroke-width="1.6"/>','<path d="M3 16c3-2 3-6 7-7s4-4 7-6" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>'];
      tiles().forEach((t, i) => list.append(h('li', {}, h('button', { type: 'button', onclick: () => ask(t.message) }, h('span', { class: 'ow-tile-i' }, icon(TI[i % 6])), h('span', { text: t.label })))));
      log.append(h('section', { class: 'ow-welcome', 'aria-labelledby': id('wh') },
        h(HL, { id: id('wh'), class: 'ow-ah', text: 'What would you like to know?' }),
        h('p', { text: 'Ask in your own words, or choose a button. I answer from sourced data about places in Cincinnati and Oxford, and I say so when I don’t know.' }), list));
      miniTiles.hidden = true;
    }
    function fillMini() {
      miniTiles.textContent = '';
      for (const t of tiles()) miniTiles.append(h('li', {}, h('button', { type: 'button', onclick: () => ask(t.message) }, t.label)));
    }
    function clearChat() { cancel(); V().stop(); welcome(); S.answers = 0; toggleSettings(false); hint('Conversation cleared.'); input.focus(); }
    const V = () => O.voice;

    function userBubble(text, hadPhoto) { const b = h('div', { class: 'ow-me' }, h('span', { class: 'ow-who', text: 'You' }), text, hadPhoto ? ' (with a photo)' : ''); log.append(b); scrollEnd(b); }

    function setBusy(b) {
      S.busy = b; sendBtn.disabled = b; stopBtn.hidden = !b; input.setAttribute('aria-busy', String(b));
    }
    function cancel() { if (S.ctrl) { S.ctrl.abort(); S.ctrl = null; } if (S.busy) { setBusy(false); const t = log.querySelector('.ow-thinking'); if (t) t.remove(); hint('Stopped.'); say('Stopped.'); } }

    async function ask(text, opts) {
      text = String(text || '').trim();
      if (S.busy) { hint('I am still working on the last question. Press Stop to cancel it.'); return; }
      const photo = S.image;
      if (!text && !photo) { hint('Type a question first, or choose a button.'); input.focus(); return; }
      if (!text && photo) text = 'What does this photo show?';
      if (!S.guided) { hint('Still loading the data. Please wait a moment and try again.'); return; }
      const welcomeEl = log.querySelector('.ow-welcome'); if (welcomeEl) { welcomeEl.remove(); fillMini(); miniTiles.hidden = false; }
      S.lastQ = text; userBubble(text, !!photo);
      const thinking = h('div', { class: 'ow-thinking' }, h('span', { class: 'ow-dots', 'aria-hidden': 'true' }, h('i'), h('i'), h('i')), h('span', { text: S.prefs.engine === 'local' && S.health && S.health.model ? 'Looking that up. The local model can take up to a minute…' : 'Looking that up…' }));
      log.append(thinking); scrollEnd(thinking); say('Looking that up.'); setBusy(true);
      S.ctrl = new g.AbortController();
      const view = newAnswerView(); let events = 0;
      try {
        const useLocal = S.prefs.engine === 'local' && S.health && S.health.model;
        const eng = useLocal ? S.local : S.guided;
        if (useLocal) S.local.fallback = S.guided;
        const gen = eng.ask(text, ctxNow(), { signal: S.ctrl.signal, image: photo ? photo.dataUrl.split(',')[1] : null });
        for await (const ev of gen) { if (thinking.isConnected && ev.type !== 'note') thinking.remove(); events++; view.handle(ev); if (S.ctrl === null) break; }
      } catch (err) { view.handle({ type: 'error', message: 'Something went wrong while looking that up.' }); }
      if (thinking.isConnected) thinking.remove();
      if (!events) view.handle({ type: 'error', message: 'I did not get an answer. Please try again.' });
      view.finish();
      S.ctrl = null; setBusy(false); S.image = null; renderAttach();
    }

    // ---- an answer on screen ----
    function newAnswerView() {
      const A = { main: '', kind: 'answer', details: [], cards: [], actions: [], unknown: null, sources: [], meta: null, clarify: null, call: null, error: null, notes: [], done: null };
      let article = null, mainP = null, cardsUl = null, headEl = null;
      const setMain = parts => { mainP.textContent = ''; mainP.append(h('span', { text: parts[0] })); if (parts.length > 1) mainP.append(' ', h('span', { class: 'ow-rest', text: parts.slice(1).join(' ') })); };
      const ensure = () => {
        if (article) return;
        S.answers++;
        headEl = h(HL, { tabindex: '-1', class: 'ow-ah', id: id('a' + S.answers), text: 'Answer' });
        mainP = h('p', { class: 'ow-main' });
        article = h('article', { class: 'ow-a', 'aria-labelledby': headEl.id }, headEl, mainP);
        log.append(article); scrollEnd(article);
      };
      const view = {
        handle(ev) {
          if (ev.type === 'note') { hint(ev.message); return; }
          ensure();
          if (ev.type === 'text') { A.main = ev.delta; A.kind = ev.kind; setMain(ev.parts || [ev.delta]); article.classList.toggle('ow-unknown-kind', ['unknown', 'no_data', 'out_of_area'].includes(ev.kind)); article.classList.toggle('ow-emergency', ev.kind === 'emergency'); }
          else if (ev.type === 'detail') A.details = ev.items;
          else if (ev.type === 'card') { A.cards.push(ev.card); if (!cardsUl) { cardsUl = h('ul', { class: 'ow-cards', 'aria-label': 'Places and events' }); article.append(cardsUl); } cardsUl.append(h('li', {}, renderCard(ev.card))); }
          else if (ev.type === 'action') A.actions.push(ev);
          else if (ev.type === 'call') A.call = ev;
          else if (ev.type === 'unknown') A.unknown = ev;
          else if (ev.type === 'sources') A.sources = ev.items;
          else if (ev.type === 'clarify') A.clarify = ev;
          else if (ev.type === 'meta') A.meta = ev;
          else if (ev.type === 'done') A.done = ev;
          else if (ev.type === 'error') { A.error = ev.message; A.kind = 'error'; setMain([ev.message]); article.classList.add('ow-unknown-kind'); }
        },
        finish() {
          ensure();
          if (A.clarify) {
            const row = h('div', { class: 'ow-clarify', role: 'group', 'aria-label': 'Choose one' });
            for (const o of A.clarify.options || []) row.append(h('button', { type: 'button', onclick: () => { if (o.action === 'locate') useLocation(() => ask(o.message)); else ask(o.message); } }, o.label));
            article.append(row);
          }
          if (A.unknown && (A.unknown.about || []).length) article.append(h('p', { class: 'ow-unknown' }, h('strong', { text: 'I don’t know: ' }), A.unknown.about.join('; ') + '.'));
          if (A.call) article.append(h('p', { class: 'ow-call' }, 'Call ' + A.call.name + ': ', h('a', { href: 'tel:' + String(A.call.phone).replace(/[^0-9+]/g, ''), text: A.call.phone })));
          if (A.error) article.append(h('div', { class: 'ow-row' }, h('button', { type: 'button', onclick: () => ask(S.lastQ) }, 'Try again')));
          if (A.kind !== 'clarify') {
            const row = h('div', { class: 'ow-row' });
            const panels = [];
            row.append(h('button', { type: 'button', onclick: e => readAloud(A, e.currentTarget) }, icon(ICONS.speaker), 'Read aloud'));
            if (A.details.length) {
              const d = h('div', { class: 'ow-detail', id: id('d' + S.answers), hidden: true }, h('ul', {}, A.details.map(t => h('li', { text: t }))));
              const b = h('button', { type: 'button', 'aria-expanded': 'false', 'aria-controls': d.id, onclick: () => { d.hidden = !d.hidden; b.setAttribute('aria-expanded', String(!d.hidden)); b.lastChild.textContent = d.hidden ? 'More detail' : 'Less detail'; } }, h('span', { text: 'More detail' }));
              row.append(b); panels.push(d);
            }
            if (A.sources.length) {
              const d = renderSources(A.sources, 's' + S.answers);
              const b = h('button', { type: 'button', 'aria-expanded': 'false', 'aria-controls': d.id, onclick: () => { d.hidden = !d.hidden; b.setAttribute('aria-expanded', String(!d.hidden)); b.lastChild.textContent = d.hidden ? 'Sources' : 'Hide sources'; } }, h('span', { text: 'Sources' }));
              row.append(b); panels.push(d);
            }
            const ids = [].concat(...A.actions.filter(a => a.action === 'show_on_map').map(a => a.ids));
            if (ids.length > 1) row.append(mapButton('Show all on map', ids));
            const rep = A.actions.find(a => a.action === 'report');
            row.append(reportButton(rep ? rep.text : 'Problem with an answer: "' + S.lastQ + '"\n'));
            article.append(row, ...panels);
          }
          if (A.meta && A.meta.as_of) article.append(h('p', { class: 'ow-asof', text: 'Data snapshot: ' + fullDate(A.meta.as_of) + '. It can be out of date, so call ahead for anything important.' }));
          if (A.done && A.done.removed) article.append(h('p', { class: 'ow-note', text: 'I removed ' + A.done.removed + ' sentence' + (A.done.removed > 1 ? 's' : '') + ' I could not check against a source.' }));
          // announce once: the headline, then how many cards
          const nCards = A.cards.length;
          say((A.kind === 'emergency' ? 'Emergency. ' : '') + (A.error ? A.error : A.main + (nCards ? ' ' + nCards + (nCards > 1 ? ' places or events are listed below.' : ' place or event is listed below.') : '')));
          if (['unknown', 'no_data'].includes(A.kind) && A.main) logGap(S.lastQ, A.unknown && A.unknown.about);
          scrollEnd(article);
        },
      };
      return view;
    }
    function logGap(q, about) {
      const gaps = readJSON('openway.gaps', []);
      gaps.push({ q: String(q).slice(0, 200), about: (about || []).slice(0, 3), t: deviceToday() });
      store.set('openway.gaps', JSON.stringify(gaps.slice(-50)));
    }
    function renderSources(items, key) {
      const ul = h('ul', {});
      for (const s of items) {
        const li = h('li', {}, h('strong', { text: s.label || 'Source' }), ' ' + (s.date ? '(' + (O.composer ? O.composer.monthYear(s.date) : s.date) + ') ' : '(no date) '),
          /^https?:/.test(s.url) ? h('a', { href: s.url, target: '_blank', rel: 'noopener noreferrer', text: 'Open the source (new tab)' }) : '');
        if (s.quote) li.append(h('blockquote', { text: '“' + s.quote + '”' }));
        ul.append(li);
      }
      return h('div', { class: 'ow-sources', id: id(key), hidden: true }, h('p', { class: 'ow-note', text: 'Quotes are word for word from the source.' }), ul);
    }
    function mapButton(label, ids, one) {
      const run = () => { if (!fire('atlas:show-places', { ids })) { g.location.href = mapUrl(ids[0]); } };
      if (mode === 'page') return h('a', { class: 'ow-btn', href: mapUrl(ids[0]), onclick: e => { if (fire('atlas:show-places', { ids })) e.preventDefault(); }, text: label });
      return h('button', { type: 'button', onclick: run, text: label });
    }
    function routeButton(pid) {
      const profile = (S.needs && (S.needs.mobility === 'cane' || (S.needs.rely || []).includes('screen_reader'))) ? 'blind' : 'wheelchair';
      if (mode === 'page') return h('a', { class: 'ow-btn', href: mapUrl(pid), onclick: e => { if (fire('atlas:route-to', { placeId: pid, profile })) e.preventDefault(); }, text: 'Route here' });
      return h('button', { type: 'button', onclick: () => { if (!fire('atlas:route-to', { placeId: pid, profile })) g.location.href = mapUrl(pid); }, text: 'Route here' });
    }
    function reportButton(text) {
      const go = () => { if (!fire('atlas:open-report', { text })) hint('To report a problem, open the place on the map and use Report a problem there.'); };
      return h('button', { type: 'button', onclick: go, text: 'Report a problem' });
    }
    function renderCard(c) {
      const el = h('section', { class: 'ow-card', 'aria-label': c.name });
      el.append(h(CH, { class: 'ow-ch', text: c.name }));
      if (c.event) {
        el.append(h('p', { class: 'ow-meta' }, h('span', { class: 'ow-when', text: c.event.title }), h('span', { text: c.event.when_text })));
        if (c.event.access.length) el.append(h('ul', { class: 'ow-chips', 'aria-label': 'Access at this event' }, c.event.access.map(a => h('li', { text: a }))));
        else el.append(h('p', { class: 'ow-src', text: 'No access details in my data. Check with the venue.' }));
      } else {
        const meta = h('p', { class: 'ow-meta' }, h('span', { class: 'ow-rate r-' + c.rating }, h('i', { 'aria-hidden': 'true', text: RATE_GLYPH[c.rating] || '?' }), (rules() && rules().RATING_TEXT[c.rating]) || c.rating));
        if (c.type) meta.append(h('span', { text: c.type }));
        if (c.distance_text) meta.append(h('span', { text: c.distance_text + ' ' + c.direction }));
        el.append(meta);
        if (c.facts.length) el.append(h('ul', { class: 'ow-facts' }, c.facts.map(f => h('li', { class: String(f.value) === 'no' ? 'no' : '' }, h('span', { class: 'ow-g', 'aria-hidden': 'true', text: String(f.value) === 'no' ? '✕' : '✓' }), f.label + ': ' + f.value + (f.detail ? ' (' + f.detail + ')' : '')))));
        for (const s of c.sources.slice(0, 2)) el.append(h('p', { class: 'ow-src', text: 'Source: ' + s.label + ', ' + (s.date ? O.composer.monthYear(s.date) : 'no date given') + '.' }));
        if (c.note) el.append(h('p', { class: 'ow-note', text: 'Note: ' + c.note }));
      }
      const row = h('div', { class: 'ow-row' });
      const hasPt = c.lat !== null && c.lat !== undefined;
      if (hasPt || (S.guided && S.guided.kb.byId.get(c.place_id))) {
        if (hasPt) row.append(routeButton(c.place_id));
        row.append(mapButton('Show on map', [c.place_id]));
      }
      if (c.phone) row.append(h('a', { class: 'ow-btn', href: 'tel:' + c.phone.replace(/[^0-9+]/g, ''), text: 'Call ' + c.phone, 'aria-label': 'Call ' + c.name + ' at ' + c.phone }));
      if (c.event && /^https?:/.test(c.event.url)) row.append(h('a', { class: 'ow-btn', href: c.event.url, target: '_blank', rel: 'noopener noreferrer', text: 'Event page (new tab)' }));
      el.append(row);
      return el;
    }

    // ---- read aloud ----
    function spoken(A) {
      const parts = [A.main];
      for (const c of A.cards) {
        if (c.event) parts.push(c.name + ': ' + c.event.title + ', ' + c.event.when_text + '.');
        else parts.push(c.name + (c.distance_text ? ', ' + c.distance_text + ' ' + c.direction : '') + '. ' + c.facts.slice(0, 2).map(f => f.label + ': ' + f.value).join('. ') + '.');
      }
      if (A.unknown && A.unknown.about && A.unknown.about.length) parts.push('I do not know: ' + A.unknown.about.join(', ') + '.');
      if (A.call) parts.push('Call ' + A.call.name + ' at ' + A.call.phone + '.');
      return parts.join(' ');
    }
    let voiceBar = null;
    function readAloud(A, btn) {
      if (!V().supportsOut()) { hint('Reading aloud is not available in this browser. Your screen reader can read the answer.'); say('Reading aloud is not available in this browser.'); return; }
      if (voiceBar) voiceBar.remove();
      const rate = h('select', { 'aria-label': 'Speaking speed', onchange: e => { S.prefs.rate = e.target.value; savePrefs(); } },
        [['0.8', 'Slow'], ['1', 'Normal'], ['1.3', 'Fast']].map(([v, l]) => h('option', { value: v, text: l, selected: String(S.prefs.rate) === v })));
      let paused = false;
      const pauseBtn = h('button', { type: 'button', onclick: () => { paused = !paused; paused ? V().pause() : V().resume(); pauseBtn.textContent = paused ? 'Resume' : 'Pause'; } }, 'Pause');
      const stop = h('button', { type: 'button', onclick: () => { V().stop(); end(); } }, 'Stop reading');
      const end = () => { if (voiceBar) { voiceBar.remove(); voiceBar = null; } if (btn.isConnected) btn.focus(); };
      voiceBar = h('div', { class: 'ow-voicebar', role: 'group', 'aria-label': 'Reading controls' }, h('span', { text: 'Reading aloud.' }), pauseBtn, stop, h('label', {}, 'Speed ', rate));
      btn.closest('.ow-a').append(voiceBar);
      V().speak(spoken(A), { rate: parseFloat(S.prefs.rate), onend: () => { if (voiceBar && voiceBar.isConnected) { voiceBar.remove(); voiceBar = null; } } });
    }

    // ---- voice in ----
    function toggleListen() {
      if (S.listening) { S.listening.stop(); return; }
      if (!V().supportsIn()) { const m = 'Voice input is not available in this browser. You can type your question, or use the dictation key on your keyboard or phone.'; hint(m); say(m); return; }
      hint('Your browser may send your voice to its maker to turn it into text.');
      S.listening = V().listen({
        onstart() { micBtn.setAttribute('aria-pressed', 'true'); micBtn.lastChild.textContent = 'Listening… stop'; say('Listening. Speak your question.'); },
        onresult(text, final) { input.value = text; if (final) { say('I heard: ' + text + '. Press Send to ask.'); } },
        onerror(m) { hint(m); say(m); },
        onend() { S.listening = null; micBtn.setAttribute('aria-pressed', 'false'); micBtn.lastChild.textContent = 'Speak'; input.focus(); },
      });
    }

    // ---- photo ----
    function localModelReady() { return S.prefs.engine === 'local' && S.health && S.health.model; }
    function pickPhoto() {
      if (!localModelReady()) { const m = 'Photo questions need the local model. Open Settings and choose Local model, or ask in words.'; hint(m); say(m); return; }
      fileInput.click();
    }
    async function onPhoto() {
      const f = fileInput.files && fileInput.files[0]; fileInput.value = '';
      if (!f) return;
      try { S.image = await O.photo.shrink(f); renderAttach(); hint('Photo ready. It is shrunk on this device and its location data is removed. Type your question, then press Send.'); input.focus(); }
      catch (e) { hint(e.message); say(e.message); }
    }
    function renderAttach() {
      attach.textContent = '';
      if (!S.image) { attach.hidden = true; return; }
      attach.hidden = false;
      attach.append(h('img', { src: S.image.dataUrl, alt: 'Your photo, shown small. It is not saved.' }), h('span', { text: 'Photo attached (not saved).' }), h('button', { type: 'button', onclick: () => { S.image = null; renderAttach(); input.focus(); } }, 'Remove photo'));
    }

    // ---- keyboard ----
    root.addEventListener('keydown', e => {
      if (e.key !== 'Escape') return;
      if (needsDlg.open) return;
      if (S.speaking || (voiceBar && voiceBar.isConnected)) { V().stop(); if (voiceBar) { voiceBar.remove(); voiceBar = null; } return; }
      if (!settings.hidden) { toggleSettings(false); settingsBtn.focus(); e.stopPropagation(); return; }
      if (mode === 'panel') { api.close(); e.stopPropagation(); }
    });
    g.addEventListener('pagehide', () => V().stop());

    // ---- boot ----
    const api = {
      ask, root,
      open() { root.hidden = false; (opener => { S.opener = opener || S.opener; })(); input.focus(); },
      close() { root.hidden = true; V().stop(); if (S.opener && S.opener.focus) S.opener.focus(); root.dispatchEvent(new g.CustomEvent('ow:closed')); },
      focus() { input.focus(); },
      state: S,
    };
    welcome(); refreshMode(); hint('Loading the data…'); sendBtn.disabled = true;
    const get = async u => { const r = await fetch(u); if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); };
    (async () => {
      try {
        const inl = g.__OPENWAY_DATA;
        const [rules, cinc, ox] = inl ? [inl.rules, inl.cincinnati, inl.oxford] : await Promise.all([get(base + 'rules.json'), get(base + 'cincinnati.json'), get(base + 'oxford.json')]);
        S.guided = new O.engine.GuidedEngine([cinc, ox], rules);
        hint(''); sendBtn.disabled = false; welcome(); root.dispatchEvent(new g.CustomEvent('ow:ready'));
        S.guided.fromData = true;
        if (S.prefs.engine === 'local') checkHealth();
        else checkHealth();
      } catch (e) {
        hint('');
        log.textContent = '';
        log.append(h('div', { class: 'ow-a ow-unknown-kind', role: 'alert' }, h(HL, { class: 'ow-ah', text: 'Problem' }), h('p', { class: 'ow-main', text: 'I could not load the data I answer from. Check your connection, then try again.' }), h('div', { class: 'ow-row' }, h('button', { type: 'button', class: 'ow-primary', onclick: () => g.location.reload() }, 'Try again'))));
      }
    })();
    return api;
  }
  O.chat = { mount };
  if (typeof module !== 'undefined') module.exports = O.chat;
})(typeof globalThis !== 'undefined' ? globalThis : this);
