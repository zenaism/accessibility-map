  // ------------------------------------------------------------------ routes and live navigation
  // Route here: the walking graph in a worker (same engine as the old Directions panel), or the saved route of the place.
  // Live position (watchPosition) and compass heading are used only while following a route; they never leave the device.
  const CORE = window.__ROUTECORE || '';
  const backends = {};
  function backend(region) {
    if (backends[region]) return backends[region];
    const url = new URL(CFG.routing.base + region + '.graph.json', location.href).href;
    const b = { url, promise: null, worker: null, G: null, next: 1, waiting: new Map() };
    const GLUE = "let G=null;self.onmessage=async(e)=>{const m=e.data;try{if(m.type==='load'){const r=await fetch(m.url);if(!r.ok)throw new Error('HTTP '+r.status);G=AtlasRoutingCore.loadGraph(await r.json());self.postMessage({type:'ready',id:m.id});}else if(m.type==='route'){self.postMessage({type:'result',id:m.id,result:AtlasDirections.route(G,...m.args)});}}catch(err){self.postMessage({type:'error',id:m.id,message:String((err&&err.message)||err)});}};";
    const ask = (msg) => new Promise((resolve, reject) => {
      const id = b.next++;
      b.waiting.set(id, { resolve, reject });
      if (b.worker) b.worker.postMessage(Object.assign({ id }, msg));
      else inline(msg).then(resolve, reject);
    });
    async function inline(msg) {
      if (!window.AtlasRoutingCore) new Function(CORE)();
      if (msg.type === 'load') { b.G = window.AtlasRoutingCore.loadGraph(await (await fetch(msg.url)).json()); return { type: 'ready' }; }
      return { type: 'result', result: window.AtlasDirections.route(b.G, ...msg.args) };
    }
    b.start = () => {
      if (b.promise) return b.promise;
      try {
        b.worker = new Worker(URL.createObjectURL(new Blob([CORE + '\n' + GLUE], { type: 'text/javascript' })));
        b.worker.onmessage = (e) => { const m = e.data, w = b.waiting.get(m.id); if (!w) return; b.waiting.delete(m.id); if (m.type === 'error') w.reject(new Error(m.message)); else w.resolve(m); };
        b.worker.onerror = () => { b.worker = null; b.promise = null; b.waiting.forEach((w) => w.reject(new Error('worker'))); b.waiting.clear(); };
      } catch (e) { b.worker = null; }
      b.promise = ask({ type: 'load', url }).then(() => b).catch((err) => { b.promise = null; throw err; });
      return b.promise;
    };
    b.route = (args) => ask({ type: 'route', args }).then((m) => m.result);
    backends[region] = b;
    return b;
  }
  const FT = 3.28084;
  const feetText = (ft) => (ft < 1000 ? Math.max(10, Math.round(ft / 10) * 10) + ' ft' : (ft / 5280).toFixed(1) + ' mi');
  // ---- spoken directions (voice.js). Off by default. The same lines the live region reads, said aloud; nothing leaves the phone.
  const VW = window.AtlasVoice.words;
  let voiceOpen = false, prevNatural = 'off';
  const VOICE = window.AtlasVoice.create({ onChange: () => { paintVoice(); const n = VOICE.state.natural; if (n !== prevNatural) { prevNatural = n; if (n === 'ready') say('Natural voice is ready.'); else if (n === 'failed') say('Natural voice did not load. The device voice is used.'); } } });
  // Voice on: speak and leave the live region alone (a screen reader would say it twice). Voice off: as before.
  const hear = (plain, spoken) => { if (VOICE.isOn()) VOICE.speak(spoken === undefined ? plain : spoken); else say(plain); };
  const stepSpeech = (i, first) => {
    const steps = N.model.steps, s = steps[i], rem = remaining(i), nxt = steps[i + 1];
    let t = first ? VW.start(s) : VW.step(s);
    if (nxt && rem <= VW.LEAD_FT + 50) { t += ' ' + VW.ahead(nxt, rem); N.aheadFor = i; }
    return t;
  };
  const cumLen = (line) => { const c = [0]; for (let i = 1; i < line.length; i++) c.push(c[i - 1] + metres([line[i - 1][1], line[i - 1][0]], [line[i][1], line[i][0]])); return c; };
  function modelFromGraph(r) {
    return { source: 'graph', line: r.line, steps: r.stepList.map((s) => ({ text: s.text, kind: s.kind, feet: s.feet, fromIdx: s.fromIdx, toIdx: s.toIdx, warnings: s.warnings })), feet: r.length_feet, compare: r.compared_with_shortest, cum: cumLen(r.line) };
  }
  // the saved route of a place has no step geometry: place step boundaries by the feet written in each step
  function modelFromSaved(it) {
    const r = it.p.getting_there.route, line = r.line, cum = cumLen(line), total = cum[cum.length - 1];
    const ft = r.directions.map((t) => { const m = /([\d,]+)\s*(?:feet|ft)/.exec(t); return m ? +m[1].replace(/,/g, '') : 0; });
    const sum = ft.reduce((a, b) => a + b, 0) || 1;
    let acc = 0;
    const steps = r.directions.map((text, i) => {
      const from = acc / sum * total; acc += ft[i]; const to = acc / sum * total;
      const idx = (d) => { let k = 0; while (k < cum.length - 1 && cum[k] < d - 0.01) k++; return k; };
      return { text, kind: i === 0 ? 'start' : 'straight', feet: ft[i], fromIdx: idx(from), toIdx: Math.max(idx(to), idx(from) + 1), warnings: [] };
    });
    steps[steps.length - 1].toIdx = line.length - 1;
    return { source: 'saved', line, steps, feet: r.length_feet, compare: r.compared_with_shortest, cum };
  }
  async function computeRoute(from, it) {
    const region = it.p.region;
    if (CFG.routing.regions.includes(region)) {
      try {
        const b = await backend(region).start();
        const r = await b.route([from[0], from[1], it.pts[0][0], it.pts[0][1], 'wheelchair']);
        if (r && !r.error) return modelFromGraph(r);
      } catch (e) { /* no graph on this copy of the site: use the saved route below */ }
    }
    return it.p.getting_there && it.p.getting_there.route && it.p.getting_there.route.line ? modelFromSaved(it) : null;
  }
  // where on the route is this position? -> {idx (segment), along (m), off (m)}
  function project(pos, model) {
    const line = model.line, r = Math.PI / 180, kx = Math.cos(pos[0] * r) * 111320, ky = 110540;
    let best = { off: Infinity, idx: 0, along: 0 };
    for (let i = 0; i < line.length - 1; i++) {
      const ax = (line[i][0] - pos[1]) * kx, ay = (line[i][1] - pos[0]) * ky, bx = (line[i + 1][0] - pos[1]) * kx, by = (line[i + 1][1] - pos[0]) * ky;
      const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy || 1e-9;
      const t = Math.max(0, Math.min(1, -(ax * dx + ay * dy) / l2));
      const off = Math.hypot(ax + t * dx, ay + t * dy);
      if (off < best.off) best = { off, idx: i, along: model.cum[i] + t * Math.sqrt(l2) };
    }
    return best;
  }
  const stepAt = (model, idx) => { const i = model.steps.findIndex((s) => idx >= s.fromIdx && idx < s.toIdx); return i < 0 ? model.steps.length - 1 : i; };

  const N = { it: null, model: null, from: null, status: 'idle', watch: null, fix: null, following: true, step: 0, auto: -1, aheadFor: -1, started: false, compass: 'unknown', heading: null, course: null, offCount: 0, past: [], detour: [], off: false, walkedTo: 0, lastAlong: 0, backCount: 0, lastOn: null, msgKind: '', msgTimer: null, lastRoute: 0, idleTimer: null, noFixTimer: null, compassTimer: null, wasActive: false, msg: '', layers: [] };
  const WRONG_WAY = 'Wrong way. Turn around.', ROUGH = 50, ARRIVE = 25, OFF = 45, IDLE_MS = 5 * 60 * 1000;
  function clearRouteLayers() { N.layers.forEach((l) => map.removeLayer(l)); N.layers = []; }
  // ---- the dots: grey for the part you walked (and any wrong turn), light blue for what is ahead, hollow grey if you are off the route
  const pointAt = (m, d) => { let i = 0; while (i < m.cum.length - 2 && m.cum[i + 1] < d) i++; const seg = m.cum[i + 1] - m.cum[i] || 1, t = Math.max(0, Math.min(1, (d - m.cum[i]) / seg)); return { i, ll: [m.line[i][1] + (m.line[i + 1][1] - m.line[i][1]) * t, m.line[i][0] + (m.line[i + 1][0] - m.line[i][0]) * t] }; };
  function walkedLL(m, wd) { const ll = m.line.map((c) => [c[1], c[0]]); if (wd <= 0.5 || ll.length < 2) return []; const k = pointAt(m, wd); return ll.slice(0, k.i + 1).concat([k.ll]); }
  function drawRoute(fitToo) {
    clearRouteLayers();
    if (!N.model) return;
    const m = N.model, ll = m.line.map((c) => [c[1], c[0]]), total = m.cum[m.cum.length - 1], wd = Math.max(0, Math.min(N.walkedTo || 0, total));
    let ahead = ll;
    if (wd > 0.5 && ll.length > 1) { const k = pointAt(m, wd); ahead = [k.ll].concat(ll.slice(k.i + 1)); }
    const cs = getComputedStyle(document.querySelector('.ax')), ring = cs.getPropertyValue('--route').trim() || '#1D4ED8', fill = cs.getPropertyValue('--route-dot').trim() || '#8EC5FF', grey = cs.getPropertyValue('--pin-unknown').trim() || '#59646C';
    const dots = (pts, color, weight) => { if (pts.length > 1) N.layers.push(L.polyline(pts, { pane: 'route', color, weight, opacity: 1, lineCap: 'round', lineJoin: 'round', dashArray: '0 15', interactive: false }).addTo(map)); };
    const walkedDots = (pts) => { dots(pts, '#fff', 12); dots(pts, grey, 8); };   // flat grey, no ring: a different shape from the dots ahead, not only a different colour
    N.past.forEach(walkedDots); walkedDots(N.detour); walkedDots(walkedLL(m, wd));
    if (N.off) { dots(ahead, '#fff', 14); dots(ahead, grey, 11); dots(ahead, '#fff', 6); }   // hollow: this route is no longer valid
    else { dots(ahead, '#fff', 17); dots(ahead, ring, 13); dots(ahead, fill, 8); }
    if (fitToo) map.fitBounds(L.latLngBounds(ll), { paddingTopLeft: [30, 150], paddingBottomRight: [30, panelHeight() + 20], maxZoom: 18, animate: !REDUCED.matches });
  }
  function resetWalk() { N.past = []; N.detour = []; N.off = false; N.walkedTo = 0; N.lastAlong = 0; N.backCount = 0; N.lastOn = null; N.msgKind = ''; clearTimeout(N.msgTimer); }
  function setMsg(text, kind, ms) { N.msg = text; N.msgKind = kind || ''; clearTimeout(N.msgTimer); if (ms) N.msgTimer = setTimeout(() => { N.msg = ''; if (S.view === 'route') navRender(); }, ms); }
  function navLeave() { navStopWatch(); clearRouteLayers(); resetWalk(); if (youMarker && N.status !== 'idle') { /* keep the dot if Near me placed it */ } N.status = 'idle'; N.it = null; N.model = null; N.fix = null; clearTimeout(N.idleTimer); window.removeEventListener('deviceorientationabsolute', onOrient, true); window.removeEventListener('deviceorientation', onOrient, true); }
  async function navOpen(it) {
    navLeave();
    N.it = it; S.it = it; N.step = 0; N.auto = -1; N.aheadFor = -1; N.started = false; N.following = true; N.msg = ''; resetWalk();
    const from = S.here || (() => { const c = map.getCenter(); return [c.lat, c.lng]; })();
    N.from = from; N.fromLabel = S.here ? 'where you were last placed' : 'the middle of the map';
    go('route');
    show('<h2 class="vh" tabindex="-1" id="h-route">Route to ' + esc(it.p.name) + '</h2>' + ui_state('Finding a route', 'Looking for a step-free way.', 'route'), { label: 'Route', title: 'Route', focus: false });
    N.model = await computeRoute(from, it);
    if (S.view !== 'route' || N.it !== it) return;
    if (!N.model) { show('<h2 class="vh" tabindex="-1" id="h-route">No route</h2>' + ui_state('No step-free route found', 'Try the directions in Google Maps instead.', 'alert') + '<a class="btn btn-secondary block" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination=' + it.pts[0][0] + ',' + it.pts[0][1] + '&travelmode=walking">' + icon('route') + '<span>Directions in Google Maps</span></a>', { label: 'Route', title: 'Route' }); return; }
    drawRoute(true);
    navRender();
  }
  const stepsList = (m, cur) => '<ol class="routelist">' + m.steps.map((s, j) => '<li' + (j === cur ? ' aria-current="step"' : '') + '>' + esc(s.text) + ' <span class="muted">' + feetText(s.feet) + '</span></li>').join('') + '</ol>';
  const allSteps = (m, cur, open) => '<details class="disc"' + (open ? ' open' : '') + '><summary>' + icon('list') + '<span>All steps</span>' + icon('down') + '</summary><div class="body">' + stepsList(m, cur) + '</div></details>';
  const privacy = '<details class="disc"><summary>' + icon('alert') + '<span>Battery and privacy</span>' + icon('down') + '</summary><div class="body"><p class="muted small">Location is on only until you stop. It stays on this device.</p></div></details>';
  const btn = (act, ic, label, kind, extra) => '<button type="button" class="btn btn-' + (kind || 'secondary') + '" data-nav="' + act + '"' + (extra || '') + '>' + icon(ic) + '<span>' + label + '</span></button>';
  const note = (ic, text) => '<div class="banner" role="status">' + icon(ic) + '<span>' + esc(text) + '</span></div>';
  function remaining(i) {
    const st = N.model.steps[i];
    if (N.fix && N.status !== 'denied') { const pr = project(N.fix, N.model); const endAlong = N.model.cum[Math.min(st.toIdx, N.model.cum.length - 1)]; return Math.max(0, Math.round((endAlong - pr.along) * FT)); }
    return st.feet;
  }
  const voiceStatus = () => {
    const v = VOICE.state;
    if (!VOICE.supported() && v.natural !== 'loading') return 'This device cannot speak. Use the written steps.';
    if (v.natural === 'loading') return 'Downloading the natural voice: ' + v.progress + '%. The device voice speaks meanwhile.';
    if (v.natural === 'ready') return 'Natural voice is ready. It works offline.';
    if (v.natural === 'failed') return 'The natural voice did not load. The device voice is used.';
    return 'Now using the voice of this device.';
  };
  const SPEEDS = [['slow', 'Slow'], ['normal', 'Normal'], ['fast', 'Fast']];
  function voiceBox() {
    const p = VOICE.state.prefs;
    return '<div id="voicebox" class="voicebox"><div class="rowbtns" style="display:grid;grid-template-columns:1fr 1fr">'
      + '<button type="button" class="btn btn-secondary" role="switch" aria-checked="' + p.on + '" data-nav="voice">' + icon(p.on ? 'volume' : 'mute') + '<span>Voice ' + (p.on ? 'on' : 'off') + '</span></button>'
      + '<button type="button" class="btn btn-secondary" data-nav="repeat">' + icon('repeat') + '<span>Repeat</span></button></div>'
      + '<details class="disc" id="voiceset"' + (voiceOpen ? ' open' : '') + '><summary>' + icon('settings') + '<span>Voice settings</span>' + icon('down') + '</summary><div class="body">'
      + '<p class="muted small" id="speedlabel">Speed</p><div class="rowbtns" role="radiogroup" aria-labelledby="speedlabel" style="display:grid;grid-template-columns:repeat(3,1fr)">'
      + SPEEDS.map((s) => '<button type="button" class="btn ' + (p.speed === s[0] ? 'btn-primary' : 'btn-secondary') + '" role="radio" aria-checked="' + (p.speed === s[0]) + '" data-nav="speed" data-speed="' + s[0] + '">' + s[1] + '</button>').join('') + '</div>'
      + '<button type="button" class="btn btn-secondary block" role="switch" aria-checked="' + !!p.natural + '" data-nav="natural" aria-describedby="voicestatus">' + icon('volume') + '<span>Natural voice (about ' + VOICE.state.size + ', once)</span></button>'
      + '<p class="muted small" id="voicestatus">' + esc(voiceStatus()) + '</p></div></details></div>';
  }
  function paintVoice() {   // update in place so the focus stays where it is
    const box = document.getElementById('voicebox'); if (!box) return;
    const p = VOICE.state.prefs, vb = box.querySelector('[data-nav=voice]'), nb = box.querySelector('[data-nav=natural]');
    vb.setAttribute('aria-checked', String(p.on)); vb.innerHTML = icon(p.on ? 'volume' : 'mute') + '<span>Voice ' + (p.on ? 'on' : 'off') + '</span>';
    box.querySelectorAll('[data-speed]').forEach((b) => { const on = b.dataset.speed === p.speed; b.setAttribute('aria-checked', String(on)); b.className = 'btn ' + (on ? 'btn-primary' : 'btn-secondary'); });
    nb.setAttribute('aria-checked', String(!!p.natural));
    box.querySelector('#voicestatus').textContent = voiceStatus();
  }
  document.addEventListener('toggle', (e) => { if (e.target && e.target.id === 'voiceset') voiceOpen = e.target.open; }, true);
  function navRender() {
    const it = N.it, m = N.model;
    if (!it || !m) return;
    const i = Math.max(0, Math.min(N.step, m.steps.length - 1)), st = m.steps[i], total = m.steps.length;
    const live = N.status === 'ok' || N.status === 'rough';
    const active = ['locating', 'ok', 'rough', 'nosignal'].includes(N.status);
    const head = '<h2 class="vh" tabindex="-1" id="h-route">Route to ' + esc(it.p.name) + '</h2>';
    const onlyHint = (t) => '<p class="muted small">' + t + '</p>';
    if (N.status === 'idle') {   // preview, before Start
      const mins = Math.max(1, Math.round(m.feet / 250));
      show(head + '<h3 class="sec" style="font-size:var(--fs-lead)">To ' + esc(it.p.name) + '</h3>'
        + '<p class="muted">' + feetText(m.feet) + ' by the step-free way, ' + total + ' steps, about ' + mins + ' min. From ' + esc(N.fromLabel) + '.' + (m.source === 'saved' ? ' Saved route.' : '') + '</p>'
        + '<p class="muted small">' + esc(m.compare || '') + ' Suggested from map data, not checked on site.</p>'
        + voiceBox() + stepsList(m, -1) + btn('start', 'route', 'Start', 'primary', ' style="width:100%"')
        + note('alert', 'Location is used only while you follow the route.'), { label: 'Route', title: 'Route', tall: true, focus: false });
      return;
    }
    if (N.status === 'stopped' || N.status === 'idleStop') {
      show(head + '<div class="state"><span class="big">' + icon(N.status === 'idleStop' ? 'clock' : 'stop') + '</span><p class="lead">' + (N.status === 'idleStop' ? 'Stopped after 5 min. Saves battery.' : 'Stopped') + '</p><p class="muted">' + (N.status === 'idleStop' ? 'Turn right when you are ready: the route stays here.' : 'Location is off. The route stays here.') + '</p></div>'
        + '<div class="rowbtns" style="display:grid;grid-template-columns:1fr 1fr">' + btn('start', 'route', 'Resume', 'primary') + (N.status === 'idleStop' ? btn('done', 'check', 'Done') : btn('steps', 'list', 'All steps')) + '</div>'
        + (N.status === 'idleStop' ? '' : '<div id="allsteps" hidden>' + stepsList(m, i) + '</div>'), { label: 'Route stopped', title: 'Route', focus: false });
      return;
    }
    if (N.status === 'arrived') {
      show(head + '<div class="state"><span class="big">' + icon('yes') + '</span><p class="lead">You are here</p><p class="muted">' + esc(m.steps[total - 1].text) + '</p></div>' + note('alert', 'Location is off.')
        + '<div class="rowbtns" style="display:grid;grid-template-columns:1fr 1fr"><button type="button" class="btn btn-secondary" data-details="' + it.i + '">' + icon('more') + '<span>Details</span></button><button type="button" class="btn btn-secondary" data-report="' + it.i + '">' + icon('report') + '<span>Report a problem</span></button></div>', { label: 'You arrived', title: 'Route', focus: true });
      return;
    }
    if (N.status === 'locating') {
      show(head + '<div class="state"><span class="big">' + icon('spinner', 'spin') + '</span><p class="lead">Finding you</p><p class="muted">First step is ready to read.</p><p class="lead" style="font-size:var(--fs-body)">' + esc(m.steps[0].text) + '</p></div>' + btn('cancel', 'close', 'Cancel') , { label: 'Finding you', title: 'Route', focus: false });
      return;
    }
    // following: the filled next-step banner (variant B) with the state line above it
    const dist = remaining(i);
    let line = '';
    if (N.status === 'denied') line = note('alert', 'Location is off. Use the steps by hand.');
    else if (N.status === 'nosignal') line = note('offline', 'No signal. Position not found.');
    else if (N.status === 'rough') line = note('alert', 'Location is rough. Arrow is off.');
    else if (N.compass === 'none') line = note('alert', 'No compass. Arrow follows your walking direction.');
    if (N.msg) line += N.msgKind === 'alert' ? note('alert', N.msg) : '<div class="banner info" role="status">' + icon('check') + '<span>' + esc(N.msg) + '</span></div>';
    if (N.compass === 'needs') line += '<button type="button" class="btn btn-secondary block" data-nav="compass">' + icon('near') + '<span>Show my direction</span></button>' + onlyHint('Your iPhone asks first. Direction stays on this device.');
    if (live && !N.following) line += '<p class="note">' + icon('near') + '<span>Map is not following you.</span></p>';
    const manual = N.status === 'denied' || N.status === 'nosignal';
    show(head + line
      + '<div class="stepcard" tabindex="0" aria-label="Next step"><span class="count">Step ' + (i + 1) + ' of ' + total + '</span><span class="dist">' + feetText(dist) + '</span><span class="what">' + icon(st.kind === 'cross' ? 'alert' : 'right') + esc(st.text) + '</span></div>'
      + '<div class="rowbtns" style="display:grid;grid-template-columns:1fr 1fr"><button type="button" class="btn btn-secondary" data-nav="prev"' + (i === 0 ? ' disabled' : '') + '>' + icon('back') + '<span>Previous</span></button><button type="button" class="btn btn-secondary" data-nav="next"' + (i === total - 1 ? ' disabled' : '') + '>' + icon('right') + '<span>Next step</span></button></div>'
      + '<div class="rowbtns" style="display:grid;grid-template-columns:1fr 1fr">' + (manual ? btn('centre', 'near', 'Start from map centre') : btn('follow', 'near', 'Follow me')) + (N.status === 'nosignal' ? btn('start', 'near', 'Try again') : btn('stop', 'stop', 'Stop', 'danger')) + '</div>'
      + (manual && N.status === 'denied' ? '<div class="rowbtns">' + btn('stop', 'close', 'Close route', 'ghost') + '</div>' : '') + voiceBox() + allSteps(m, i, false) + privacy, { label: 'Route', title: 'Route', focus: false });
  }
  // ---- watching the position
  function navStopWatch() { if (N.watch != null && navigator.geolocation) navigator.geolocation.clearWatch(N.watch); N.watch = null; clearTimeout(N.noFixTimer); clearTimeout(N.compassTimer); }
  function touch() { clearTimeout(N.idleTimer); if (N.watch != null) N.idleTimer = setTimeout(() => { navStopWatch(); N.status = 'idleStop'; navRender(); hear('Stopped after 5 minutes to save battery.'); }, IDLE_MS); }
  function noFixWait() { clearTimeout(N.noFixTimer); N.noFixTimer = setTimeout(() => { if (N.watch != null && N.status !== 'nosignal') { N.status = 'nosignal'; if (S.view === 'route') navRender(); hear('No signal. Position not found.'); } }, 15000); }
  function navStart() {
    navStopWatch();
    N.status = 'locating'; N.fix = null; N.offCount = 0; navRender(); hear('Finding you.');
    if (!navigator.geolocation) { N.status = 'denied'; navRender(); return; }
    noFixWait();
    N.watch = navigator.geolocation.watchPosition(onFix, (err) => {
      if (err.code === 1) { navStopWatch(); N.status = 'denied'; navRender(); hear('Location is off. Use the steps by hand.'); return; }
      if (!N.fix && N.status !== 'nosignal') { N.status = 'nosignal'; navRender(); hear('No signal. Position not found.'); }   // keep watching: a later fix recovers by itself
    }, { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 });
    startCompass(); touch();
  }
  async function onFix(pos) {
    noFixWait();
    const c = pos.coords, here = [c.latitude, c.longitude], first = !N.fix;
    N.fix = here; S.here = here; N.course = c.heading != null && !isNaN(c.heading) ? c.heading : N.course;
    N.status = c.accuracy > ROUGH ? 'rough' : 'ok';
    drawYou(here, c.accuracy, N.status === 'rough' ? null : (N.compass === 'on' ? N.heading : N.course));
    const dest = N.it.pts[0];
    if (metres(here, dest) < ARRIVE) { arrive(); return; }
    if (first) {
      const start = N.model.line[0];
      if (metres(here, [start[1], start[0]]) > 30) { const m = await computeRoute(here, N.it); if (m && m.steps.length) { N.model = m; drawRoute(false); } }
    }
    const pr = project(here, N.model), total = N.model.cum[N.model.cum.length - 1];
    if (metres(here, [N.model.line[N.model.line.length - 1][1], N.model.line[N.model.line.length - 1][0]]) < ARRIVE || pr.along > total - ARRIVE) { arrive(); return; }
    const auto = stepAt(N.model, pr.idx);
    if (auto !== N.auto) { const first = !N.started; N.started = true; N.auto = auto; N.step = auto; N.aheadFor = -1; hear('Step ' + (auto + 1) + ' of ' + N.model.steps.length + '. ' + N.model.steps[auto].text, VOICE.isOn() ? stepSpeech(auto, first) : ''); }
    else if (VOICE.isOn() && N.aheadFor !== auto && N.model.steps[auto + 1] && remaining(auto) <= VW.LEAD_FT) { N.aheadFor = auto; VOICE.speak(VW.ahead(N.model.steps[auto + 1], remaining(auto))); }
    if (pr.off <= OFF) {   // on the route
      N.offCount = 0;
      if (N.off) { N.off = false; setMsg('', ''); drawRoute(false); }   // back on the old route
      N.detour = [];
      N.lastOn = here;
      N.backCount = pr.along < N.lastAlong - 8 ? N.backCount + 1 : (pr.along > N.lastAlong - 3 ? 0 : N.backCount);
      N.lastAlong = pr.along;
      const wt = Math.max(0, pr.along - 8);   // a dot turns grey only when you are clearly past it (phone position is off by 5 to 20 m)
      if (Math.abs(wt - (N.walkedTo || 0)) > 2) { N.walkedTo = wt; drawRoute(false); }
      if (N.backCount >= 3) { if (N.msg !== WRONG_WAY) { setMsg(WRONG_WAY, 'alert'); hear(WRONG_WAY); } }
      else if (N.msg === WRONG_WAY) setMsg('', '');
    } else if (N.status === 'ok') {   // off the route
      N.offCount++;
      if (!N.detour.length && N.lastOn) N.detour.push(N.lastOn);
      N.detour.push(here);
      if (N.offCount >= 2 && !N.off) { N.off = true; setMsg('You left the route. Finding a new way…', 'alert'); say('You left the route. Finding a new way.'); }
      if (N.off) drawRoute(false);
      if (N.offCount >= 2 && Date.now() - N.lastRoute > 15000) {
        N.lastRoute = Date.now();
        const m = await computeRoute(here, N.it);
        if (m && m.source === 'graph' && m.steps.length) {
          N.past.push(walkedLL(N.model, N.walkedTo || 0), N.detour.slice());   // what you walked, wrong turn included, stays grey
          N.detour = []; N.off = false; N.offCount = 0; N.model = m; N.walkedTo = 0; N.lastAlong = 0; N.backCount = 0; N.auto = -1; N.aheadFor = -1; N.step = 0;
          setMsg('New route from where you are.', 'ok', 5000); drawRoute(false); hear('New route from where you are.');
        } else setMsg('No step-free way found from here. Go back to the grey dots, or use Google Maps.', 'alert');
      }
    }
    if (N.following && S.view === 'route') followPan(here);
    if (S.view === 'route') navRender();
    touch();
  }
  function followPan(pos) {   // keep the dot in the part of the map the panel does not cover
    const z = map.getZoom();
    map.setView(map.unproject(map.project(L.latLng(pos), z).add([0, panelHeight() / 2 - 20]), z), z, { animate: !REDUCED.matches });
  }
  function arrive() { navStopWatch(); N.walkedTo = N.model ? N.model.cum[N.model.cum.length - 1] : 0; N.off = false; if (N.model) drawRoute(false); N.status = 'arrived'; navRender(); hear('You are here. ' + N.model.steps[N.model.steps.length - 1].text, VW.arrive(N.it.p.name)); }
  // ---- compass
  function onOrient(e) {
    let h = null;
    if (typeof e.webkitCompassHeading === 'number') h = e.webkitCompassHeading;
    else if (e.absolute && e.alpha != null) h = (360 - e.alpha) % 360;
    else if (e.type === 'deviceorientationabsolute' && e.alpha != null) h = (360 - e.alpha) % 360;
    if (h == null) return;
    N.heading = h; N.compass = 'on'; clearTimeout(N.compassTimer);
    if (N.fix && N.status === 'ok') drawYou(N.fix, null, h);
  }
  const IOS = /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  function startCompass() {
    if (typeof DeviceOrientationEvent === 'undefined') { N.compass = 'none'; return; }
    if (IOS && typeof DeviceOrientationEvent.requestPermission === 'function') { if (N.compass !== 'on') N.compass = 'needs'; return; }   // iOS: needs a tap
    N.compass = 'unknown';
    window.addEventListener('deviceorientationabsolute', onOrient, true);
    window.addEventListener('deviceorientation', onOrient, true);
    N.compassTimer = setTimeout(() => { if (N.compass !== 'on') { N.compass = 'none'; if (S.view === 'route') navRender(); } }, 2500);
  }
  function askCompass() {
    DeviceOrientationEvent.requestPermission().then((r) => { if (r === 'granted') { N.compass = 'unknown'; window.addEventListener('deviceorientation', onOrient, true); N.compassTimer = setTimeout(() => { if (N.compass !== 'on') { N.compass = 'none'; navRender(); } }, 2500); } else N.compass = 'none'; navRender(); }, () => { N.compass = 'none'; navRender(); });
  }
  // ---- controls
  document.addEventListener('click', (e) => {
    const t = e.target.closest('[data-nav]'); if (!t || !N.it) return;
    const a = t.dataset.nav, total = N.model ? N.model.steps.length : 0;
    touch();
    if (a === 'start') { VOICE.unlock(); N.following = true; navStart(); }
    else if (a === 'voice') { VOICE.setOn(!VOICE.isOn()); if (VOICE.isOn()) VOICE.speak('Voice on.'); else say('Voice off.'); }
    else if (a === 'repeat') { VOICE.unlock(); if (!VOICE.repeat(N.model ? VW.step(N.model.steps[Math.max(0, Math.min(N.step, N.model.steps.length - 1))]) : '')) say('Nothing to repeat yet.'); }
    else if (a === 'speed') { VOICE.setSpeed(t.dataset.speed); if (VOICE.isOn()) VOICE.speak('This is the ' + t.dataset.speed + ' speed.'); }
    else if (a === 'natural') { VOICE.setNatural(!VOICE.state.prefs.natural); }
    else if (a === 'cancel') { navStopWatch(); N.status = 'idle'; navRender(); }
    else if (a === 'stop') { navStopWatch(); clearTimeout(N.idleTimer); if (N.status === 'denied') { N.status = 'idle'; back(); return; } N.status = 'stopped'; navRender(); hear('Stopped. Location is off.'); const b = $('[data-nav=start]'); if (b) b.focus(); }
    else if (a === 'done') { back(); }
    else if (a === 'steps') { const el = $('#allsteps'); el.hidden = !el.hidden; }
    else if (a === 'prev' || a === 'next') { N.step = Math.max(0, Math.min(total - 1, N.step + (a === 'next' ? 1 : -1))); navRender(); const b = $('[data-nav=' + a + ']:not([disabled])') || $('.stepcard'); b.focus(); hear('Step ' + (N.step + 1) + ' of ' + total + '. ' + N.model.steps[N.step].text, VW.step(N.model.steps[N.step])); }
    else if (a === 'follow') { N.following = true; if (N.fix) followPan(N.fix); navRender(); const b = $('[data-nav=follow]'); if (b) b.focus(); }
    else if (a === 'centre') { const c = map.getCenter(); N.from = [c.lat, c.lng]; computeRoute(N.from, N.it).then((m) => { if (m) { N.model = m; N.step = 0; drawRoute(true); } navRender(); }); }
    else if (a === 'compass') askCompass();
  });
  map.on('dragstart', () => { if (S.view === 'route' && N.following && (N.status === 'ok' || N.status === 'rough')) { N.following = false; navRender(); } });
  ['pointerdown', 'keydown'].forEach((ev) => document.addEventListener(ev, () => { if (S.view === 'route') touch(); }, true));
  // stop watching while the page is hidden (battery); pick up again when it is shown
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && N.watch != null) { N.wasActive = true; navStopWatch(); }
    else if (!document.hidden && N.wasActive && S.view === 'route' && ['ok', 'rough', 'locating', 'nosignal'].includes(N.status)) { N.wasActive = false; navStart(); }
  });
  window.AtlasNav = { N, project, modelFromSaved, onFix, navStart, VOICE };
