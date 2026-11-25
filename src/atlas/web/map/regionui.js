  // ------------------------------------------------------------------ cities: the region as a variable (B4)
  // Order of choice: ?region= in the address (this visit only), then the choice saved on this device, then the closest
  // covered city found on the device (asked once), then the Choose a city list. The position never leaves the device.
  const CATALOG = window.__REGIONS || [];
  const REG = new Map(CATALOG.map((r) => [r.id, r]));
  const RKEY = 'atlas-region';
  const cityName = (id) => (REG.get(id) || {}).short || id;
  const LOADED = new Set(Object.keys(DATA));
  const urlRegion = (() => { const v = new URLSearchParams(location.search).get('region'); return REG.has(v) ? v : null; })();
  const tierOf = (id) => (REG.get(id) || {}).tier || 'full';
  const isLimited = (id) => tierOf(id) === 'limited';

  async function ensureData(id) {
    if (LOADED.has(id)) return;
    const r = REG.get(id);
    if (!r.has_detail) { DATA[id] = { features: [], generated: asOf }; addItems(id, DATA[id]); LOADED.add(id); return; }   // a limited city with no mapped places yet
    const res = await fetch(id + '_atlas.geojson', { cache: 'no-cache' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const fc = await res.json();
    DATA[id] = fc; addItems(id, fc); LOADED.add(id);
  }
  function setUrl(id) {
    try { const u = new URL(location.href); u.searchParams.set('region', id); history.replaceState(null, '', u.pathname + u.search + u.hash); } catch (e) { /* file:// or old browser */ }
  }
  const pill = $('#region-pill');
  let pillTimer = null;
  function showPill(kind, text, action) {
    clearTimeout(pillTimer);
    pill.hidden = false; pill.className = 'regionpill ' + kind; pill.textContent = '';
    pill.append(h('span', { class: 'pilltxt' }, kind === 'loading' ? icon('spinner', 'spin') : kind === 'failed' ? icon('alert') : icon('check'), text), action || '');
    if (kind === 'done') pillTimer = setTimeout(() => { pill.hidden = true; }, 3500);
  }
  function h(tag, props, ...kids) {
    const el = document.createElement(tag);
    for (const k of Object.keys(props || {})) { const v = props[k]; if (v === null || v === undefined || v === false) continue; if (k === 'class') el.className = v; else el.setAttribute(k, v === true ? '' : v); }
    for (const kid of kids.flat()) { if (kid === null || kid === undefined || kid === false) continue; if (typeof kid === 'string' && kid.startsWith('<svg')) { const t = document.createElement('template'); t.innerHTML = kid; el.append(t.content.firstChild); } else el.append(kid.nodeType ? kid : document.createTextNode(String(kid))); }
    return el;
  }

  /** Change the city in place. Keeps the old map until the new one is ready; an open search keeps its words. */
  async function switchTo(id, o) {
    o = o || {};
    if (!REG.has(id)) return false;
    if (id === S.region && !o.force) { hidePop(); return true; }
    const was = S.region;
    showPill('loading', 'Loading ' + cityName(id));
    say('Loading ' + cityName(id) + '.');
    try { await ensureData(id); }
    catch (e) {
      showPill('failed', 'Could not load ' + cityName(id) + (was ? '. You are still in ' + cityName(was) + '.' : '.'), h('button', { type: 'button', class: 'btn btn-secondary', 'data-city-retry': id }, 'Try again'));
      say('Could not load ' + cityName(id) + '.');
      return false;
    }
    S.region = id; S.regionFrom = o.from || 'switch';
    if (o.save !== false) store.set(RKEY, id);
    if (o.url !== false) setUrl(id);
    const r = REG.get(id);
    clearSel(); shownKey = ''; S.az = false; S.near = false; S.it = null; S.here = null;
    map.setView(r.center, r.zoom || 12, { animate: false });
    updateCityButtons(); hidePop();
    if (was && was !== id && S.q.trim()) { S.kept = { from: was }; S.prev = []; S.view = 'results'; S.shown = 10; }
    else { S.kept = null; S.prev = []; S.view = 'start'; S.q = ''; q.value = ''; S.type = null; }
    render();
    if (o.silent) pill.hidden = true; else showPill('done', 'Showing ' + cityName(id));
    say('Showing ' + cityName(id) + '.');
    atlas.emit('atlas:region-changed', { region: id });
    return true;
  }

  // ---- the city list (plain list, variant A): bottom sheet on phones, dropdown on desktop
  function coverageRow(r) {
    return '<span class="nm">' + esc(r.name.replace(/, .*/, '')) + '</span>' + (r.tier === 'limited' ? '<span class="badge unknown">' + icon('info') + '<span>Limited data</span></span>' : '<span></span>') + '<span class="sub">' + esc(r.coverage) + '</span>';
  }
  function cityListHtml(selected) {
    const full = CATALOG.filter((r) => r.tier === 'full'), lim = CATALOG.filter((r) => r.tier === 'limited');
    const row = (r) => '<button type="button" class="listrow' + (r.id === selected ? ' sel' : '') + '" role="radio" aria-checked="' + (r.id === selected) + '" data-city="' + r.id + '">' + coverageRow(r) + '</button>';
    return '<div class="stack" role="radiogroup" aria-label="Cities">' + full.map(row).join('') + '</div>'
      + (lim.length ? '<h3 class="sec">Limited data</h3><div class="stack" role="radiogroup" aria-label="Cities with limited data">' + lim.map(row).join('') + '</div>' : '')
      + '<p class="muted small">More cities coming.</p>';
  }
  let citySheet = null, popOpen = false;
  function openCities(btn) {
    if (PHONE.matches) {
      const node = document.createElement('div'); node.className = 'stack3'; node.innerHTML = cityListHtml(S.region);
      citySheet = ui.sheet.open({ title: 'Choose a city', node, onClose: () => { citySheet = null; btn.setAttribute('aria-expanded', 'false'); } });
      btn.setAttribute('aria-expanded', 'true');
    } else {
      const pop = $('#city-pop');
      if (!pop.hidden) { hidePop(); return; }
      pop.innerHTML = '<h2 class="vh" id="city-pop-h" tabindex="-1">Choose a city</h2>' + cityListHtml(S.region);
      pop.hidden = false; popOpen = true; btn.setAttribute('aria-expanded', 'true');
      const first = pop.querySelector('[aria-checked=true]') || pop.querySelector('[data-city]'); if (first) first.focus();
    }
  }
  function hidePop() { const pop = $('#city-pop'); if (pop && !pop.hidden) { pop.hidden = true; popOpen = false; const b = $('#city-btn-d'); if (b) { b.setAttribute('aria-expanded', 'false'); if (document.activeElement === document.body || pop.contains(document.activeElement)) b.focus(); } } if (citySheet) citySheet.close(); }
  function updateCityButtons() {
    const name = S.region ? cityName(S.region) : 'Choose city';
    for (const b of document.querySelectorAll('.city-btn')) {
      b.querySelector('.cn').textContent = name;
      b.setAttribute('aria-label', (S.region ? name + ', change city' : 'Choose a city'));
    }
  }
  document.addEventListener('click', (e) => {
    const cb = e.target.closest('.city-btn'); if (cb) { openCities(cb); return; }
    const pick = e.target.closest('[data-city]');
    if (pick) { const id = pick.dataset.city; if (document.querySelector('.sheet.modal') && citySheet) citySheet.close(); if (S.view === 'choose') { S.view = 'start'; } switchTo(id); return; }
    const retry = e.target.closest('[data-city-retry]'); if (retry) { switchTo(retry.dataset.cityRetry); return; }
    if (popOpen && !e.target.closest('#city-pop')) hidePop();
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && popOpen) { e.preventDefault(); hidePop(); } });

  // ---- first open and the Choose a city view
  function viewChoose(why) {
    $('#hint').hidden = true;
    const msg = why === 'denied' ? 'Location is off. Pick a city.' : why === 'outside' ? 'You seem to be outside our cities.' : 'Pick the city you want to see.';
    show('<h2 id="h-choose" tabindex="-1">Choose a city</h2><p class="muted">' + esc(msg) + '</p>' + cityListHtml(S.region), { label: 'Choose a city', title: 'Choose city', tall: true });
    $('#back').hidden = true;
  }
  function viewUseCity(r) {
    $('#hint').hidden = true;
    show('<h2 id="h-use" tabindex="-1">You seem to be in ' + esc(r.short) + '.</h2><p class="lead" style="font-size:var(--fs-body)">Use ' + esc(r.short) + '?</p>'
      + '<div class="rowbtns" style="display:grid;grid-template-columns:1fr 1fr"><button type="button" class="btn btn-primary" data-use-city="' + r.id + '">' + icon('check') + '<span>Use ' + esc(r.short) + '</span></button><button type="button" class="btn btn-secondary" data-other-city>' + icon('list') + '<span>Choose another</span></button></div>'
      + '<p class="note">' + icon('pin') + '<span>Your position stays on this device.</span></p>', { label: 'Use this city?', title: 'Choose city' });
    $('#back').hidden = true;
  }
  function viewLocating() {
    show('<h2 class="vh" id="h-loc" tabindex="-1">Finding your city</h2>' + ui_state('Finding your city', 'Looking for the closest city we cover. Your position stays on this device.', 'near'), { label: 'Finding your city', focus: false });
  }
  async function bootRegion() {
    const saved = store.get(RKEY);
    if (urlRegion) {
      const prev = saved && REG.has(saved) && saved !== urlRegion ? saved : null;
      const ok = await switchTo(urlRegion, { save: false, url: false, silent: true, from: 'link' });
      if (ok && prev) { S.linkBanner = { prev }; render(); }
      return ok;
    }
    if (saved && REG.has(saved)) return switchTo(saved, { save: false, url: false, silent: true, from: 'saved' });
    S.view = 'locating'; render(); updateCityButtons();
    const fallback = (why) => { S.view = 'choose'; S.chooseWhy = why; render(); };
    if (!navigator.geolocation) return fallback('denied');
    navigator.geolocation.getCurrentPosition(async (p) => {
      const c = AtlasRegion.closest(CATALOG, p.coords.latitude, p.coords.longitude);
      if (!c) return fallback('outside');
      try { await ensureData(c.id); } catch (e) { return fallback('choose'); }
      map.setView(c.center, c.zoom || 12, { animate: false });
      S.view = 'usecity'; S.useCity = c; render();
    }, () => fallback('denied'), { timeout: 6000, maximumAge: 600000 });
  }

  // ---- limited data notice
  const noticeKey = (id) => 'atlas-notice-' + id;
  function limitedNotice() {
    const r = REG.get(S.region);
    if (!r || r.tier !== 'limited' || store.get(noticeKey(r.id))) return '';
    return '<div class="banner info" role="note">' + icon('info') + '<span><b>Less data here</b><br>' + esc(r.coverage + '. Ratings not open yet.') + '</span><button type="button" class="btn btn-secondary" data-dismiss-notice="' + r.id + '">Got it</button></div>';
  }
  function placeNotice(it) {
    const r = REG.get(it.p.region);
    if (!r || r.tier !== 'limited') return '';
    return '<div class="banner info" role="note">' + icon('info') + '<span><b>Less data here</b><br>No rating yet.' + (routeOn(it) ? '' : ' No route yet.') + '</span></div>';
  }
  function linkBannerHtml() {
    if (!S.linkBanner) return '';
    return '<div class="banner info" role="status">' + icon('pin') + '<span>This link is in ' + esc(cityName(S.region)) + '.</span><button type="button" class="btn btn-secondary" data-back-city="' + S.linkBanner.prev + '">Back to ' + esc(cityName(S.linkBanner.prev)) + '</button></div>';
  }
  document.addEventListener('click', (e) => {
    const u = e.target.closest('[data-use-city]'); if (u) { S.view = 'start'; switchTo(u.dataset.useCity); return; }
    if (e.target.closest('[data-other-city]')) { S.view = 'choose'; S.chooseWhy = 'choose'; render(); return; }
    const d = e.target.closest('[data-dismiss-notice]'); if (d) { store.set(noticeKey(d.dataset.dismissNotice), '1'); render(); return; }
    const b = e.target.closest('[data-back-city]'); if (b) { S.linkBanner = null; switchTo(b.dataset.backCity); return; }
    const s = e.target.closest('[data-search-other]'); if (s) { switchTo(s.dataset.searchOther); return; }
    if (e.target.closest('[data-stay-city]')) { S.near = false; S.view = S.prevView || 'start'; render(); return; }
    const sw = e.target.closest('[data-switch-near]'); if (sw) { const id = sw.dataset.switchNear; S.view = 'start'; switchTo(id).then(() => nearMe()); return; }
    if (e.target.closest('[data-choose-city]')) { S.view = 'choose'; S.chooseWhy = 'choose'; render(); return; }
  });
