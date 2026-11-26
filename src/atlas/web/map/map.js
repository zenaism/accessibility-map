/* Map app (session B1). Plain ES2019, no build step. Uses the B0 foundation (atlas.ui, atlasTheme, atlas events).
   Data: DATA = {region: FeatureCollection}. Location, saved places and the current view never leave the device. */
(function () {
  'use strict';
  const CFG = window.__MAPCFG, DATA = window.__MAPDATA;
  const ui = atlas.ui, icon = ui.icon, esc = ui.esc;
  const $ = (s, r) => (r || document).querySelector(s);
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); return true; } catch (e) { return false; } },
  };
  const RK = { accessible: 'yes', partial: 'partial', not_accessible: 'no', unknown: 'unknown' };
  const WORD = { yes: 'Accessible', partial: 'Partly accessible', no: 'Not accessible', unknown: 'Not known' };
  const HELP = {
    yes: 'Step-free entry and an accessible restroom are stated, or the trail is paved.',
    partial: 'Some access features are stated.',
    no: 'A source says it is not accessible.',
    unknown: 'No source yet. This does not mean it is inaccessible.',
  };
  const LAYER = { culture: 'Museum or attraction', park: 'Park or garden', restroom: 'Restroom', adaptive_recreation: 'Adaptive recreation', lodging: 'Lodging', event: 'Event venue', building: 'Building', food_drink: 'Food and drink', service: 'Shop or service', trail: 'Trail' };
  const RANK = { yes: 0, partial: 1, no: 2, unknown: 3 };
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const rating = (it) => RK[it.p.access_rating] || 'unknown';
  const badge = (k) => ui.badge(k, WORD[k]);

  // ------------------------------------------------------------------ items
  const ITEMS = [], byId = new Map();
  let n = 0, markersReady = false;
  function addItems(region, fc) {
    for (const f of fc.features) {
      const p = f.properties;
      const pts = p.layer === 'trail'
        ? (f.geometry.type === 'LineString' ? [f.geometry.coordinates] : (f.geometry.coordinates || [])).flat().map((c) => [c[1], c[0]])
        : [[f.geometry.coordinates[1], f.geometry.coordinates[0]]];
      p.region = p.region || region;
      const it = { i: n++, p, f, pts, dist: null, marker: null, text: (p.name + ' ' + (p.summary || '') + ' ' + (LAYER[p.layer] || '')).toLowerCase() };
      ITEMS.push(it); byId.set(p.link_id, it);
      if (markersReady) makeMarker(it);
    }
    if (markersReady) adoptFavRegions();
  }
  for (const region of Object.keys(DATA)) addItems(region, DATA[region]);
  const asOf = Object.values(DATA)[0].generated;

  // ------------------------------------------------------------------ small helpers
  function metres(a, b) {
    const R = 6371000, r = Math.PI / 180, dLa = (b[0] - a[0]) * r, dLo = (b[1] - a[1]) * r;
    const h = Math.sin(dLa / 2) ** 2 + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLo / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  }
  const fmtDist = (m) => (m < 300 ? Math.max(50, Math.round((m * 3.28084) / 50) * 50) + ' ft' : (m / 1609.34).toFixed(m < 16000 ? 1 : 0) + ' mi');
  const fmtMonth = (s) => { const m = /^(\d{4})-(\d{2})/.exec(s || ''); return m ? MON[+m[2] - 1] + ' ' + m[1] : ''; };
  const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (e) { return ''; } };
  const layerLabel = (it) => LAYER[it.p.layer] || 'Place';
  const keyVal = (it, name) => { const k = (it.p.keys || []).find((x) => x[0].toLowerCase() === name); return k ? k[1] : null; };
  const factsFor = (it, re) => (it.p.facts || []).filter((f) => re.test(f.attribute));

  // "Open now" from OSM-style hours. Only simple patterns are understood; anything else means "not known", never "open".
  const DAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
  function openNow(hours, when) {
    if (!hours) return null;
    const h = String(hours).trim();
    if (h === '24/7') return true;
    const d = (when.getDay() + 6) % 7, minutes = when.getHours() * 60 + when.getMinutes();
    let open = null;
    for (const seg of h.split(';').map((s) => s.trim()).filter(Boolean)) {
      const m = /^((?:Mo|Tu|We|Th|Fr|Sa|Su)(?:-(?:Mo|Tu|We|Th|Fr|Sa|Su))?(?:,(?:Mo|Tu|We|Th|Fr|Sa|Su)(?:-(?:Mo|Tu|We|Th|Fr|Sa|Su))?)*)\s+(off|closed|\d{1,2}:\d{2}-\d{1,2}:\d{2}(?:,\d{1,2}:\d{2}-\d{1,2}:\d{2})*)$/i.exec(seg);
      if (!m) return null;
      let hit = false;
      for (const part of m[1].split(',')) {
        const [a, b] = part.split('-'), i = DAYS.indexOf(a), j = b ? DAYS.indexOf(b) : i;
        hit = hit || (i <= j ? d >= i && d <= j : d >= i || d <= j);
      }
      if (!hit) continue;
      if (/^(off|closed)$/i.test(m[2])) { open = false; continue; }
      open = m[2].split(',').some((r) => {
        const [s, e] = r.split('-').map((t) => { const [x, y] = t.split(':'); return +x * 60 + +y; });
        return s <= e ? minutes >= s && minutes < e : minutes >= s || minutes < e;
      });
    }
    return open;
  }

  // ------------------------------------------------------------------ place types (tiles and chips)
  const TYPES = [
    { id: 'restrooms', label: 'Restrooms', icon: 'toilet', test: (it) => it.p.layer === 'restroom' },
    { id: 'parking', label: 'Parking', icon: 'parking', test: (it) => factsFor(it, /parking/i).some((f) => f.value === 'yes') || keyVal(it, 'parking') === 'yes' },
    { id: 'entrances', label: 'Entrances', icon: 'door', test: (it) => keyVal(it, 'entrance') === 'yes' },
    { id: 'parks', label: 'Parks', icon: 'map', test: (it) => it.p.layer === 'park' },
    { id: 'trails', label: 'Trails', icon: 'route', test: (it) => it.p.layer === 'trail' },
    { id: 'open', label: 'Open now', icon: 'clock', test: (it) => openNow(it.p.details && it.p.details.hours, new Date()) === true },
  ];

  // ------------------------------------------------------------------ saved places (device only)
  const FAV_KEY = 'atlas-favs', FAV2_KEY = 'atlas-favs-v2', SNAP_KEY = 'atlas-fav-snap', LINK_KEY = 'atlas-fav-link';
  const readJson = (k, d) => { try { return JSON.parse(store.get(k)) || d; } catch (e) { return d; } };
  // saved places are {id, region} in atlas-favs-v2; atlas-favs keeps the plain ids for the old page. Old lists are migrated:
  // the region of an old id is looked up in the loaded data (see adoptFavRegions) and is filled in as soon as it is known.
  const FREG = {};
  let FAVS = [];
  (function readFavs() {
    const v2 = readJson(FAV2_KEY, null);
    if (Array.isArray(v2)) { for (const x of v2) if (x && typeof x.id === 'string') { FAVS.push(x.id); if (x.region) FREG[x.id] = x.region; } }
    else FAVS = readJson(FAV_KEY, []).filter((x) => typeof x === 'string');
  })();
  function adoptFavRegions() {
    let changed = false;
    for (const id of FAVS) { if (!FREG[id] && byId.has(id)) { FREG[id] = byId.get(id).p.region; changed = true; } }
    if (changed) persist();
  }
  const favRegion = (id) => FREG[id] || (SNAP[id] && SNAP[id].g) || null;
  let SNAP = readJson(SNAP_KEY, {});
  let storageOk = true;
  const isFav = (it) => FAVS.includes(it.p.link_id);
  const snapOf = (it) => ({ n: it.p.name, r: it.p.access_rating, g: it.p.region, t: Date.now(), k: JSON.stringify(it.p.keys || []) });
  function persist() {
    storageOk = store.set(FAV2_KEY, JSON.stringify(FAVS.map((id) => ({ id, region: FREG[id] || null })))) && store.set(FAV_KEY, JSON.stringify(FAVS)) && store.set(SNAP_KEY, JSON.stringify(SNAP));
  }
  function setFav(it, on) {
    const id = it.p.link_id;
    if (on && !FAVS.includes(id)) { FAVS.push(id); FREG[id] = it.p.region; SNAP[id] = snapOf(it); bumpChanges(); }
    if (!on && FAVS.includes(id)) { FAVS = FAVS.filter((x) => x !== id); delete SNAP[id]; delete FREG[id]; bumpChanges(); }
    persist();
    refreshPins();
  }
  function bumpChanges() { const l = readJson(LINK_KEY, null); if (l) { l.c = (l.c || 0) + 1; store.set(LINK_KEY, JSON.stringify(l)); } }
  // what changed since the place was saved: shown as "Needs a look"
  function lookReason(id) {
    const it = byId.get(id), s = SNAP[id];
    if (!it && favRegion(id) && !LOADED.has(favRegion(id))) return '';   // that city is not loaded yet: nothing is known to have changed
    if (!it) return s ? 'No longer in the data. Report if wrong.' : 'No longer in the data.';
    if (!s) return '';
    if (s.r !== it.p.access_rating) return 'Rating changed from ' + (WORD[RK[s.r]] || 'Not known') + ' to ' + WORD[rating(it)] + '.';
    if (s.k !== JSON.stringify(it.p.keys || [])) return 'Details changed since you saved it.';
    return '';
  }
  function restoreLink() {
    return location.href.split('#')[0] + '#saved=' + FAVS.map(encodeURIComponent).join(',');   // restore links carry ids only; the cities are looked up on the device
  }

  // ------------------------------------------------------------------ map
  const PHONE = window.matchMedia('(max-width: 899px)');
  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)');
  const map = L.map('map', { zoomControl: false, keyboard: true, zoomAnimation: !REDUCED.matches, fadeAnimation: !REDUCED.matches });
  const firstRegion = Object.keys(DATA)[0];
  map.setView(CFG.view[firstRegion] ? CFG.view[firstRegion][0] : [39.5, -84.7], CFG.view[firstRegion] ? CFG.view[firstRegion][1] : 12);
  L.tileLayer('https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18, maxNativeZoom: 16 }).addTo(map);
  const cluster = L.markerClusterGroup({
    showCoverageOnHover: false, maxClusterRadius: 45, disableClusteringAtZoom: 15,
    iconCreateFunction: (c) => L.divIcon({ className: 'pinwrap', iconSize: [44, 44], html: '<div class="cluster">' + c.getChildCount() + '</div>' }),
  }).addTo(map);
  const trails = L.layerGroup().addTo(map);
  const paneRoute = map.createPane('route'); paneRoute.style.zIndex = 450;
  const paneYou = map.createPane('you'); paneYou.style.zIndex = 650;
  let selected = null, shownKey = '', youMarker = null, youRing = null, routeLayers = [];

  function pinIcon(it, sel) {
    const k = rating(it), fav = isFav(it);
    return L.divIcon({
      className: 'pinwrap', iconSize: [38, 38], iconAnchor: [19, 19],
      html: '<div class="pin ' + k + (sel ? ' sel' : '') + '">' + icon(k) + '</div>' + (fav ? '<span class="pinfav" style="position:absolute;right:-6px;top:-6px;width:18px;height:18px;border-radius:50%;background:#fff;border:2px solid #11181D;display:grid;place-items:center;color:#B3167B">' + icon('save').replace('class="ic"', 'class="ic" style="width:11px;height:11px;fill:currentColor"') + '</span>' : ''),
    });
  }
  function makeMarker(it) {
    if (it.p.layer === 'trail') {
      const col = { yes: '#0072B2', partial: '#E69F00', no: '#B84A00', unknown: '#59646C' }[rating(it)];
      it.marker = L.geoJSON(it.f, { style: { color: col, weight: 5, opacity: 0.9 } });
      it.marker.on('click', () => openPlace(it));
    } else {
      it.marker = L.marker(it.pts[0], { icon: pinIcon(it, false), keyboard: false, title: it.p.name });
      it.marker.on('click', () => openPlace(it));
    }
  }
  ITEMS.forEach(makeMarker);
  markersReady = true;
  adoptFavRegions();
  function syncMap(list) {
    const key = list.map((it) => it.i).join(',');
    if (key === shownKey) return;
    shownKey = key;
    const on = new Set(list);
    cluster.clearLayers();
    cluster.addLayers(ITEMS.filter((it) => it.p.layer !== 'trail' && on.has(it)).map((it) => it.marker));
    ITEMS.filter((it) => it.p.layer === 'trail').forEach((it) => (on.has(it) ? trails.addLayer(it.marker) : trails.removeLayer(it.marker)));
  }
  function refreshPins() { ITEMS.forEach((it) => { if (it.p.layer !== 'trail') it.marker.setIcon(pinIcon(it, it === selected)); }); }
  function select(it) {
    const prev = selected; selected = it;
    if (prev && prev.p.layer !== 'trail') prev.marker.setIcon(pinIcon(prev, false));
    if (it && it.p.layer !== 'trail') it.marker.setIcon(pinIcon(it, true));
  }
  function panelHeight() { return PHONE.matches ? ($('#panel').offsetHeight || 260) : 0; }
  function fit(list, maxZoom) {
    const pts = list.flatMap((it) => it.pts);
    if (!pts.length) return;
    const b = L.latLngBounds(pts);
    const opt = { paddingTopLeft: [30, PHONE.matches ? 150 : 40], paddingBottomRight: [30, panelHeight() + 20], maxZoom: maxZoom || 16, animate: !REDUCED.matches };
    if (pts.length === 1) map.setView(pts[0], Math.max(map.getZoom(), 16), { animate: !REDUCED.matches });
    else map.fitBounds(b, opt);
  }
  function centreOn(it) {
    if (it.p.layer === 'trail') return fit([it], 15);
    const z = Math.max(map.getZoom(), 16);
    const target = map.project(L.latLng(it.pts[0]), z).add([0, panelHeight() / 2 - 20]);
    map.setView(map.unproject(target, z), z, { animate: !REDUCED.matches });
  }
  function drawYou(pos, acc, heading) {
    if (youMarker) map.removeLayer(youMarker);
    youMarker = L.marker(pos, { pane: 'you', keyboard: false, interactive: false, icon: L.divIcon({ className: 'pinwrap', iconSize: [1, 1], html: '<div class="you">' + (heading != null ? '<div class="cone" style="transform:rotate(' + Math.round(heading) + 'deg)"></div>' : '') + '<div class="dot"></div></div>' }) }).addTo(map);
    if (youRing) map.removeLayer(youRing);
    if (acc) youRing = L.circle(pos, { radius: acc, color: '#B3167B', weight: 1.5, fillColor: '#B3167B', fillOpacity: 0.12, pane: 'you', interactive: false }).addTo(map);
  }
  $('#zin').onclick = () => map.zoomIn();
  $('#zout').onclick = () => map.zoomOut();
  // markers are mouse and touch only: keyboard and screen-reader users get the list, which has the same content
  new MutationObserver(() => document.querySelectorAll('#map .leaflet-marker-icon:not([data-q])').forEach((e) => { e.setAttribute('tabindex', '-1'); e.setAttribute('aria-hidden', 'true'); e.dataset.q = 1; })).observe($('#map'), { childList: true, subtree: true });

  // ------------------------------------------------------------------ state and panel
  const S = { region: null, regionFrom: null, kept: null, linkBanner: null, savedFilter: false, chooseWhy: '', useCity: null, prevView: 'start', view: 'start', q: '', type: null, shown: 10, here: null, near: false, az: false, edit: false, prev: [], it: null, more: false, step: 0 };
  const panel = $('#panel'), body = $('#panel-body'), live = $('#live');
  const say = (t) => { live.textContent = ''; setTimeout(() => { live.textContent = t; }, 30); };
  function show(html, o) {
    o = o || {};
    body.innerHTML = html;
    const showBack = !(S.view === 'start' || S.view === 'results' && !S.prev.length);
    if (showBack) body.insertAdjacentHTML('afterbegin', '<div class="backrow only-desktop"><button type="button" class="btn btn-ghost" data-back>' + icon('back') + '<span>Back</span></button></div>');
    panel.classList.toggle('tall', !!o.tall);
    panel.setAttribute('aria-label', o.label || 'Places');
    $('#appbar-title').textContent = o.title || 'Accessibility Map';
    $('#back').hidden = S.view === 'start' || S.view === 'results' && !S.prev.length;
    ui.setTab(S.view === 'saved' ? 'saved' : 'map');
    body.scrollTop = 0;
    const h = $('h2[tabindex="-1"]', body);
    if (h && o.focus !== false) h.focus({ preventScroll: true });
  }
  function go(view, o) {
    o = o || {};
    if (o.push !== false && S.view !== view) S.prev.push({ view: S.view, it: S.it, q: S.q, type: S.type });
    S.view = view;
    render();
  }
  function back() {
    if (S.view === 'route' && typeof navLeave === 'function') navLeave();
    const p = S.prev.pop();
    if (!p) { S.view = 'start'; S.q = ''; S.type = null; clearSel(); render(); return; }
    S.view = p.view; S.it = p.it; S.q = p.q; S.type = p.type; $('#q').value = S.q;
    if (S.view !== 'card' && S.view !== 'details' && S.view !== 'route') clearSel();
    render();
  }
  function clearSel() { select(null); if (typeof navLeave === 'function') navLeave(); }

  // ------------------------------------------------------------------ search and results
  function results() {
    const t = S.q.trim().toLowerCase();
    let list = ITEMS.filter((it) => it.p.region === S.region && (!S.type || TYPES.find((x) => x.id === S.type).test(it)) && (!t || t.split(/\s+/).every((w) => it.text.includes(w))));
    if (S.here) list.forEach((it) => { it.dist = Math.min(...it.pts.map((p) => metres(S.here, p))); });
    const nameCmp = (a, b) => a.p.name.localeCompare(b.p.name, undefined, { sensitivity: 'base', numeric: true });
    if (S.az) list.sort(nameCmp);
    else list.sort((a, b) => RANK[rating(a)] - RANK[rating(b)] || (S.here ? a.dist - b.dist : 0) || nameCmp(a, b));
    if (S.near && S.here) list.sort((a, b) => a.dist - b.dist);
    return list;
  }
  const rowSub = (it) => layerLabel(it) + (it.dist != null ? ' · ' + fmtDist(it.dist) + (S.near ? '' : ' straight line') : '');
  function viewStart() {
    syncMap([]); $('#hint').hidden = false;
    show('<h2 class="vh" id="h-start" tabindex="-1">Start</h2>' + linkBannerHtml() + limitedNotice()
      + '<a class="savedrow" href="#saved" data-go="saved">' + icon('save') + '<span>Saved places</span><span class="cnt">' + FAVS.length + ' saved</span>' + icon('right') + '</a>'
      + '<p class="lead" style="font-size:var(--fs-body)">Search, or pick a type.</p>'
      + '<div class="tile-grid three" role="group" aria-label="Place types">' + TYPES.map((t) => '<button type="button" class="tile sm" data-type="' + t.id + '">' + icon(t.icon) + '<span>' + t.label + '</span></button>').join('') + '</div>'
      + '<button type="button" class="btn btn-ghost" data-az style="justify-self:start">Browse A to Z</button>', { label: 'Start', focus: false });
  }
  function viewResults() {
    $('#hint').hidden = true;
    const list = results();
    syncMap(list);
    if (!list.length) {
      show('<h2 class="vh" id="h-res" tabindex="-1">No places</h2>' + ui_state('No places match', S.q ? 'Nothing matches “' + esc(S.q) + '”. Try fewer words, or pick a type.' : 'Nothing in this type yet. Try another type.', 'search')
        + '<button type="button" class="btn btn-secondary block" data-clear>' + icon('close') + '<span>Clear search</span></button>', { label: 'Results', focus: false });
      say('No places match.');
      return;
    }
    const shown = list.slice(0, S.shown);
    show('<div class="head-row"><h2 id="h-res" tabindex="-1">' + list.length + ' place' + (list.length === 1 ? '' : 's') + '</h2><button type="button" class="btn btn-ghost" data-go="legend">' + icon('list') + '<span>Legend</span></button></div>'
      + (S.kept ? '<div class="banner info" role="status">' + icon('check') + '<span>Showing ' + esc(cityName(S.region)) + '. Your search stays. Results are for ' + esc(cityName(S.region)) + ' now.</span><button type="button" class="btn btn-secondary" data-search-other="' + S.kept.from + '">Search ' + esc(cityName(S.kept.from)) + ' instead</button></div>' : '')
      + '<p class="muted small">' + (S.az ? 'A to Z.' : S.near ? 'Nearest first.' : 'Best known first' + (S.here ? ', then nearest.' : '.')) + '</p>'
      + '<div class="chip-row" role="group" aria-label="Place types">' + TYPES.map((t) => ui_chip(t, S.type === t.id)).join('') + '</div>'
      + '<ul class="plain" id="rows">' + shown.map((it) => '<li><button type="button" class="listrow' + (it === selected ? ' sel' : '') + '" data-open="' + it.i + '"><span class="nm">' + esc(it.p.name) + '</span>' + badge(rating(it)) + '<span class="sub">' + esc(rowSub(it)) + '</span></button></li>').join('') + '</ul>'
      + (list.length > shown.length ? '<button type="button" class="btn btn-secondary block" data-more>Show ' + Math.min(10, list.length - shown.length) + ' more</button>' : ''), { label: 'Results', focus: false, tall: true });
    say(list.length + ' place' + (list.length === 1 ? '' : 's') + (S.q ? ' matching ' + S.q : '') + '.');
  }
  const ui_chip = (t, on) => '<button type="button" class="chip" data-type="' + t.id + '" aria-pressed="' + on + '">' + icon('check', 'tick') + '<span>' + t.label + '</span></button>';
  const ui_state = (title, text, ic) => '<div class="state"><span class="big">' + icon(ic) + '</span><p class="lead">' + title + '</p><p class="muted">' + text + '</p></div>';

  // ------------------------------------------------------------------ place card and details
  function sourceLine(it) {
    const hosts = [...new Set((it.p.facts || []).map((f) => host(f.source)).filter(Boolean))];
    const when = fmtMonth(it.p.newest_source);
    return hosts.length || when ? (hosts[0] || 'Sources') + ', ' + (when || 'no date given') : 'No source yet';
  }
  const confLine = (it) => { const s = new Set((it.p.facts || []).map((f) => f.source).filter(Boolean)); return s.size ? 'Confirmed by ' + s.size + ' source' + (s.size > 1 ? 's' : '') + '.' : ''; };
  const KEYWORD = { yes: 'Yes', partly: 'Partly', no: 'No', 'not known': 'Not known' };
  function stat(it, label, icn, re) {
    const f = factsFor(it, re)[0], k = keyVal(it, label.toLowerCase());
    let v = k ? KEYWORD[k] : 'Not known';
    if (label === 'Entrance' && k === 'yes') v = 'Step-free';
    if (f && f.detail && label === 'Parking' && k === 'yes') { const m = /(\d+)\s+(?:accessible|reserved|designated)/i.exec(f.detail); if (m) v = m[1] + ' reserved'; }
    return '<div class="stat">' + icon(icn) + '<span class="k">' + label + '</span><span class="v">' + esc(v) + '</span></div>';
  }
  const routeOn = (it) => CFG.routing.regions.includes(it.p.region) && !!(it.p.getting_there && it.p.getting_there.route && it.p.getting_there.route.line);
  const saveBtn = (it) => '<button type="button" class="btn btn-secondary" data-save="' + it.i + '" aria-pressed="' + isFav(it) + '">' + icon('save').replace('class="ic"', 'class="ic" ' + (isFav(it) ? 'style="fill:currentColor"' : '')) + '<span>' + (isFav(it) ? 'Saved' : 'Save') + '</span></button>';
  function viewCard(it) {
    $('#hint').hidden = true;
    const k = rating(it);
    show(linkBannerHtml() + placeNotice(it) + '<div class="place">'
      + '<div style="display:flex;gap:12px;align-items:center"><span class="ratetile ' + k + '">' + icon(k) + '</span><div style="display:grid;gap:6px;min-width:0"><h2 class="name" tabindex="-1" id="h-card">' + esc(it.p.name) + '</h2>' + badge(k) + '</div></div>'
      + '<div class="stat3">' + stat(it, 'Entrance', 'door', /entrance|door/i) + stat(it, 'Restroom', 'toilet', /restroom|toilet/i) + stat(it, 'Parking', 'parking', /parking/i) + '</div>'
      + '<p class="conf">' + icon('clock') + '<span>' + esc(sourceLine(it)) + '</span></p>'
      + (routeOn(it) ? '<button type="button" class="btn btn-primary block" data-route="' + it.i + '">' + icon('route') + '<span>Route here</span></button>' : '<a class="btn btn-primary block" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination=' + it.pts[0][0] + ',' + it.pts[0][1] + '&travelmode=walking">' + icon('route') + '<span>Directions in Google Maps</span><span class="vh"> (opens in a new tab)</span></a>')
      + '<div class="rowbtns" style="display:grid;grid-template-columns:1fr 1fr auto">' + saveBtn(it) + '<button type="button" class="btn btn-secondary" data-details="' + it.i + '">' + icon('info') + '<span>More details</span></button><button type="button" class="btn btn-secondary btn-icon" data-copy="' + it.i + '" aria-label="Copy link to ' + esc(it.p.name) + '">' + icon('share') + '</button></div></div>', { label: it.p.name });
  }
  function dfact(it, label, icn, re) {
    const f = factsFor(it, re)[0], k = keyVal(it, label.toLowerCase());
    if (!f && (!k || k === 'not known')) {
      return '<div class="dfact">' + icon(icn) + '<div><div class="k">' + label + '</div><div class="v">Not known</div></div><span></span><div class="nx">Call to ask, or report what you saw.</div></div>';
    }
    const word = f ? (f.detail || f.value) : KEYWORD[k];
    return '<div class="dfact">' + icon(icn) + '<div><div class="k">' + label + '</div><div class="v">' + esc(String(word).slice(0, 120)) + '</div></div><span></span>'
      + (f && f.quote ? '<div class="q">“' + esc(f.quote.slice(0, 200)) + '” ' + esc((f.source ? host(f.source) : '') + (f.date ? ', ' + fmtMonth(f.date) : '')) + '</div>' : '') + '</div>';
  }
  function moreHtml(it) {
    const p = it.p, g = p.getting_there || {}, d = p.details || {};
    let h = '';
    const other = (p.facts || []).filter((f) => !/entrance|door|restroom|toilet|parking/i.test(f.attribute));
    if (other.length) h += '<h3 class="sec">Other facts</h3>' + other.map((f) => '<div class="dfact">' + icon('info') + '<div><div class="k">' + esc(f.attribute) + '</div><div class="v">' + esc(f.detail || f.value) + '</div></div><span></span>' + (f.source ? '<div class="q"><a href="' + esc(f.source) + '" target="_blank" rel="noopener">' + esc(host(f.source)) + '<span class="vh"> (opens in a new tab)</span></a>' + (f.date ? ', ' + esc(fmtMonth(f.date)) : '') + '</div>' : '') + '</div>').join('');
    const r = g.route;
    if (r && r.directions) h += '<h3 class="sec">Route steps from ' + esc(r.from) + '</h3><p class="muted small">About ' + r.length_feet.toLocaleString() + ' feet. ' + esc(r.compared_with_shortest || '') + '</p><ol class="routelist">' + r.directions.map((s) => '<li>' + esc(s) + '</li>').join('') + '</ol><p class="muted small">Suggested from map data, not checked on site.</p>';
    if (g.arrival || g.bus_stop) h += '<h3 class="sec">Getting there</h3><ul class="plain">' + (g.arrival ? '<li>' + esc(g.arrival) + '</li>' : '') + (g.bus_stop ? '<li>Nearest bus stop: ' + esc(g.bus_stop.name) + ', about ' + Math.round(g.bus_stop.metres * 3.28084 / 50) * 50 + ' ft</li>' : '') + '</ul>';
    const rows = [];
    if (d.address) rows.push('<li>Address: ' + esc(d.address) + '</li>');
    if (d.phone) rows.push('<li>Phone: <a href="tel:' + esc(String(d.phone).replace(/[^+\d]/g, '')) + '">' + esc(d.phone) + '</a></li>');
    if (d.website) rows.push('<li><a href="' + esc(d.website) + '" target="_blank" rel="noopener">Website<span class="vh"> (opens in a new tab)</span></a></li>');
    if (d.hours) rows.push('<li>Hours: ' + esc(d.hours) + '</li>');
    if (rows.length) h += '<h3 class="sec">Address, phone and hours</h3><ul class="plain">' + rows.join('') + '</ul><p class="muted small">Check before you go.</p>';
    if (p.notice) h += '<div class="banner" role="note">' + icon('alert') + '<span>Notice: ' + esc(p.notice) + '</span></div>';
    h += '<div class="rowbtns"><a class="btn btn-secondary" href="places/' + esc(p.region) + '/' + esc(p.link_id) + '.html">' + icon('list') + '<span>Text-only page</span></a><button type="button" class="btn btn-secondary" data-copy="' + it.i + '">' + icon('share') + '<span>Copy link</span></button></div>';
    return h;
  }
  function viewDetails(it) {
    const k = rating(it);
    show(linkBannerHtml() + placeNotice(it) + '<div style="display:flex;gap:12px;align-items:center"><span class="ratetile ' + k + '">' + icon(k) + '</span><div style="display:grid;gap:6px;min-width:0"><h2 class="name" tabindex="-1" id="h-det">' + esc(it.p.name) + '</h2>' + badge(k) + '</div></div>'
      + (confLine(it) ? '<p class="conf">' + icon('check') + '<span>' + esc(confLine(it)) + '</span></p>' : '')
      + '<p class="conf">' + icon('clock') + '<span>' + esc(sourceLine(it)) + '</span></p>'
      + '<div class="rowbtns" style="display:grid;grid-template-columns:' + (routeOn(it) ? '2fr 1fr' : '1fr') + '">' + (routeOn(it) ? '<button type="button" class="btn btn-primary" data-route="' + it.i + '">' + icon('route') + '<span>Route here</span></button>' : '') + saveBtn(it) + '</div>'
      + '<h3 class="sec">Access facts</h3>' + dfact(it, 'Entrance', 'door', /entrance|door/i) + dfact(it, 'Restroom', 'toilet', /restroom|toilet/i) + dfact(it, 'Parking', 'parking', /parking/i)
      + '<button type="button" class="btn btn-secondary block" data-more-details aria-expanded="' + S.more + '" aria-controls="more-det">' + icon(S.more ? 'down' : 'plus') + '<span>' + (S.more ? 'Fewer details' : 'More details') + '</span></button>'
      + '<div id="more-det" class="stack3"' + (S.more ? '' : ' hidden') + '>' + (S.more ? moreHtml(it) : '') + '</div>'
      + '<button type="button" class="btn btn-ghost" data-report="' + it.i + '" style="justify-self:start">' + icon('report') + '<span>Report a problem here</span></button>', { label: it.p.name + ' details', tall: true, title: 'Place details' });
  }
  function openPlace(it, o) {
    o = o || {};
    S.it = it; S.more = false;
    select(it);
    if (o.centre !== false) centreOn(it);
    go(o.details ? 'details' : 'card');
  }

/*__VOICE__*/
/*__NAV__*/
/*__REGION__*/
  // ------------------------------------------------------------------ legend
  function viewLegend() {
    show('<div class="head-row"><h2 id="h-leg" tabindex="-1">Legend</h2></div>'
      + ['yes', 'partial', 'no', 'unknown'].map((k) => '<div class="legendrow"><div class="pin ' + k + '" style="position:relative">' + icon(k) + '</div><div>' + badge(k) + '<div class="muted small">' + HELP[k] + '</div></div></div>').join('')
      + '<div class="legendrow"><div class="cluster" style="position:relative">5</div><div>Group of nearby places. Zoom in to separate them.</div></div>'
      + '<div class="legendrow"><div class="you" style="width:44px;height:30px;position:relative"><div class="dot" style="left:22px;top:15px"></div></div><div>Your location, only if you share it.</div></div>'
      + '<p class="muted small">Basemap: U.S. Geological Survey, The National Map. Data: OpenStreetMap, Overture Maps, venue and agency websites. Data last updated ' + esc(asOf) + '.</p>', { label: 'Legend', title: 'Legend', tall: true });
  }

  // ------------------------------------------------------------------ saved places
  const cityTag = (id) => { const r = favRegion(id); return r ? '<span class="citytag">' + esc(cityName(r)) + '</span>' : ''; };
  function favRow(id) {
    const it = byId.get(id), reason = lookReason(id), s = SNAP[id];
    const name = it ? it.p.name : (s && s.n) || 'A saved place';
    const k = it ? rating(it) : s ? (RK[s.r] || 'unknown') : null;
    const sub = (k ? badge(k) : '') + (it ? '<span>' + esc(layerLabel(it) + (S.here ? ' · ' + fmtDist(Math.min(...it.pts.map((p) => metres(S.here, p)))) : '')) + '</span>' : '');
    const other = !it && favRegion(id) && !LOADED.has(favRegion(id));
    const openBtn = it ? '<button type="button" class="btn btn-icon btn-ghost" data-open="' + it.i + '" aria-label="Open ' + esc(name) + '">' + icon('right') + '</button>'
      : other ? '<button type="button" class="btn btn-icon btn-ghost" data-open-saved="' + esc(id) + '" aria-label="Open ' + esc(name) + ' in ' + esc(cityName(favRegion(id))) + '">' + icon('right') + '</button>' : '<span></span>';
    return '<li class="favrow' + (reason ? ' look' : '') + '"><span class="nm">' + esc(name) + cityTag(id) + '</span>'
      + (S.edit ? '<button type="button" class="btn btn-icon btn-ghost" data-unsave="' + esc(id) + '" aria-label="Remove ' + esc(name) + '">' + icon('trash') + '</button>' : openBtn)
      + (reason ? '<span class="sub" style="flex-wrap:nowrap;align-items:flex-start">' + icon('alert') + '<span>' + esc(reason) + '</span></span>' : '<span class="sub">' + sub + '</span>') + '</li>';
  }
  const isSafari = /^((?!chrome|android|crios|fxios).)*safari/i.test(navigator.userAgent);
  function viewSaved() {
    $('#hint').hidden = true;
    const cities = [...new Set(FAVS.map(favRegion).filter(Boolean))];
    const shownIds = S.savedFilter && S.region ? FAVS.filter((id) => favRegion(id) === S.region || !favRegion(id)) : FAVS, hiddenN = FAVS.length - shownIds.length;
    const look = shownIds.filter(lookReason), rest = shownIds.filter((id) => !look.includes(id));
    const link = readJson(LINK_KEY, null);
    let h = '<h2 class="vh" id="h-saved" tabindex="-1">Saved places</h2>';
    if (!storageOk) h += '<div class="banner" role="status">' + icon('alert') + '<span>This browser would not keep your saved places. Copy your restore link.</span></div>';
    else if (isSafari && FAVS.length) h += '<div class="banner" role="status">' + icon('alert') + '<span>Safari may clear saved places after 7 days away. Copy your link now.</span></div>';
    if (!FAVS.length) {
      h += ui_state('No saved places yet', 'Tap Save on a place to keep it here, on this device only.', 'save')
        + '<div class="opt stack"><label class="lbl" for="rl">Have a restore link?</label><input class="input" id="rl" placeholder="Paste it here" autocomplete="off"><span class="hint">It stays on this device.</span><button type="button" class="btn btn-secondary" data-restore-paste>' + icon('check') + '<span>Restore</span></button></div>';
    } else {
      h += '<p class="muted" role="status">' + (S.savedFilter && S.region ? shownIds.length + ' saved in ' + esc(cityName(S.region)) : FAVS.length + ' saved place' + (FAVS.length > 1 ? 's' : '') + (cities.length > 1 ? ' in ' + cities.length + ' cities' : '')) + '</p>';
      if (S.region && (cities.length > 1 || S.savedFilter)) h += '<div class="chip-row" role="group" aria-label="City filter"><button type="button" class="chip" data-saved-filter aria-pressed="' + S.savedFilter + '">' + icon('check', 'tick') + '<span>Show only ' + esc(cityName(S.region)) + '</span></button></div>';
      if (look.length) h += '<h3 class="groupt">' + icon('alert') + 'Needs a look · ' + look.length + '</h3><ul class="plain">' + look.map(favRow).join('') + '</ul>';
      h += '<h3 class="groupt">All places · ' + rest.length + '</h3><ul class="plain' + (FAVS.length > 12 ? ' compact' : '') + '">' + rest.map(favRow).join('') + '</ul>'
        + '<div class="rowbtns" style="display:grid;grid-template-columns:1fr 1fr"><button type="button" class="btn btn-secondary" data-edit aria-pressed="' + S.edit + '">' + icon(S.edit ? 'check' : 'list') + '<span>' + (S.edit ? 'Done' : 'Edit list') + '</span></button><button type="button" class="btn btn-secondary" data-sketch>' + icon('map') + '<span>Sketch map</span></button></div>'
        + '<button type="button" class="btn btn-secondary block" data-copy-restore>' + icon('share') + '<span>Copy restore link</span></button>'
        + (hiddenN ? '<p class="note">' + icon('info') + '<span>' + hiddenN + ' saved in another city ' + (hiddenN > 1 ? 'are' : 'is') + ' hidden.</span></p>' : '') + (cities.length > 1 || hiddenN ? '<p class="note">' + icon('info') + '<span>Open a place in another city and the map switches to that city.</span></p>' : '')
        + (link ? '<p class="note">' + icon('clock') + '<span>Link last copied ' + ago(link.t) + '.' + (link.c ? ' ' + link.c + ' change' + (link.c > 1 ? 's' : '') + ' since.' : '') + '</span></p>' : '');
    }
    show(h, { label: 'Saved places', title: 'Saved places', tall: true });
    $('#back').hidden = false;
  }
  function ago(t) { const d = Math.floor((Date.now() - t) / 864e5); return d <= 0 ? 'today' : d === 1 ? 'yesterday' : d + ' days ago'; }
  function viewRestore(ids) {
    const have = new Set(FAVS), fresh = ids.filter((x) => !have.has(x)), known = ids.filter((x) => byId.has(x));
    S.restore = { ids: known, mode: 'add' };
    show('<h2 id="h-restore" tabindex="-1">Restore saved places?</h2><p class="muted">Your list has ' + FAVS.length + '. The link has ' + ids.length + ': ' + fresh.length + ' new' + (known.length < ids.length ? ', ' + (ids.length - known.length) + ' no longer in the data' : '') + '.</p>'
      + '<div role="radiogroup" aria-label="How to restore" class="stack"><button type="button" class="choice" role="radio" data-value="add" aria-checked="true" tabindex="0"><span>Add to my list</span><span class="mark">' + icon('check') + '</span></button><button type="button" class="choice" role="radio" data-value="replace" aria-checked="false" tabindex="-1"><span>Replace my list</span><span class="mark">' + icon('check') + '</span></button></div>'
      + '<div class="rowbtns" style="display:grid;grid-template-columns:1fr 1fr"><button type="button" class="btn btn-secondary" data-restore-cancel>' + icon('close') + '<span>Cancel</span></button><button type="button" class="btn btn-primary" data-restore-do>' + icon('check') + '<span>Restore</span></button></div>', { label: 'Restore saved places', title: 'Restore' });
  }
  function parseRestore(text) {
    const m = /#saved=([^#\s]*)/.exec(text) || (/^[\w%.,~-]+$/.test(text.trim()) ? [0, text.trim()] : null);
    return m ? m[1].split(',').map((x) => { try { return decodeURIComponent(x); } catch (e) { return ''; } }).filter(Boolean) : null;
  }

  // ------------------------------------------------------------------ suggestions (combobox)
  const q = $('#q'), sug = $('#sug');
  let sugIdx = -1, sugRows = [];
  function suggest() {
    const t = q.value.trim().toLowerCase();
    if (!t) return closeSug();
    const types = TYPES.filter((x) => x.label.toLowerCase().includes(t)).map((x) => ({ kind: 'type', id: x.id, label: x.label, sub: ITEMS.filter((it) => it.p.region === S.region && x.test(it)).length + ' places', icon: x.icon }));
    const layers = [...new Set(ITEMS.filter((it) => it.p.region === S.region).map((it) => it.p.layer))].filter((l) => LAYER[l].toLowerCase().includes(t)).map((l) => ({ kind: 'layer', id: l, label: LAYER[l], sub: ITEMS.filter((it) => it.p.region === S.region && it.p.layer === l).length + ' places', icon: 'search' }));
    const places = results().slice(0, 4).map((it) => ({ kind: 'place', it, label: it.p.name, sub: it.dist != null ? fmtDist(it.dist) : layerLabel(it), icon: 'pin' }));
    sugRows = [...types, ...layers, ...places];
    if (!sugRows.length) return closeSug();
    sugIdx = 0;
    const tp = sugRows.filter((r) => r.kind !== 'place'), pl = sugRows.filter((r) => r.kind === 'place');
    const row = (r) => '<div class="opt-row" role="option" id="o' + sugRows.indexOf(r) + '" aria-selected="' + (sugRows.indexOf(r) === sugIdx) + '" data-sug="' + sugRows.indexOf(r) + '">' + icon(r.icon) + '<span><b>' + esc(r.label) + '</b><small>' + esc(r.sub) + '</small></span>' + (r.kind === 'place' ? badge(rating(r.it)) : '<span></span>') + '</div>';
    sug.innerHTML = (tp.length ? '<div class="gh" role="presentation">Types</div>' + tp.map(row).join('') : '') + (pl.length ? '<div class="gh" role="presentation">Places</div>' + pl.map(row).join('') : '');
    sug.hidden = false; q.setAttribute('aria-expanded', 'true'); q.setAttribute('aria-activedescendant', 'o' + sugIdx);
  }
  function closeSug() { sug.hidden = true; sug.innerHTML = ''; q.setAttribute('aria-expanded', 'false'); q.removeAttribute('aria-activedescendant'); sugRows = []; sugIdx = -1; }
  function chooseSug(i) {
    const r = sugRows[i]; if (!r) return;
    closeSug();
    if (r.kind === 'place') { q.value = r.label; S.q = r.label; S.type = null; openPlace(r.it); return; }
    if (r.kind === 'type') { S.type = r.id; S.q = ''; q.value = ''; } else { S.q = r.label.split(' ')[0]; q.value = S.q; }
    S.shown = 10; S.near = false; S.az = false; S.it = null; clearSel(); go('results'); fit(results());
  }
  function runSearch() {
    closeSug(); S.q = q.value; S.shown = 10; S.near = false; S.az = false; S.type = null; clearSel();
    if (!S.q.trim()) { S.prev = []; go('start', { push: false }); return; }
    go('results', { push: false }); fit(results());
  }
  q.addEventListener('input', () => { $('#qclear').hidden = !q.value; $('#filter').hidden = !!q.value; suggest(); });
  q.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (sug.hidden) return; e.preventDefault();
      sugIdx = (sugIdx + (e.key === 'ArrowDown' ? 1 : -1) + sugRows.length) % sugRows.length;
      sug.querySelectorAll('[role=option]').forEach((o, i) => o.setAttribute('aria-selected', String(i === sugIdx)));
      q.setAttribute('aria-activedescendant', 'o' + sugIdx);
    } else if (e.key === 'Enter') { e.preventDefault(); if (!sug.hidden && sugIdx >= 0 && sugRows.length && e.shiftKey === false && document.activeElement === q && q.dataset.pick === '1') chooseSug(sugIdx); else runSearch(); }
    else if (e.key === 'Escape') { if (!sug.hidden) { e.preventDefault(); closeSug(); } }
    else q.dataset.pick = '0';
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') q.dataset.pick = '1';
  });
  sug.addEventListener('mousedown', (e) => e.preventDefault());
  sug.addEventListener('click', (e) => { const r = e.target.closest('[data-sug]'); if (r) chooseSug(+r.dataset.sug); });
  $('#qclear').addEventListener('click', () => { q.value = ''; $('#qclear').hidden = true; $('#filter').hidden = false; closeSug(); S.q = ''; S.type = null; S.prev = []; S.it = null; clearSel(); S.view = 'start'; render(); q.focus(); });
  $('#filter').addEventListener('click', () => { S.type = null; go('results'); });

  // ------------------------------------------------------------------ near me
  function nearMe() {
    const done = (pos, acc, note) => { S.here = pos; S.near = true; S.az = false; S.q = ''; q.value = ''; S.type = null; S.shown = 10; drawYou(pos, acc); clearSel(); go('results'); fit(results().slice(0, 6), 16); say(note); };
    const centre = () => { const c = map.getCenter(); done([c.lat, c.lng], 0, 'Location not shared. Distances are from the middle of the map.'); };
    // Near me asks before the map jumps to another city (the check is on this device)
    const check = (p) => {
      const c = AtlasRegion.closest(CATALOG, p.coords.latitude, p.coords.longitude);
      if (c && c.id === S.region) return done([p.coords.latitude, p.coords.longitude], p.coords.accuracy, 'Measured from your location. Distances are straight lines.');
      S.nearCity = c ? c.id : null; S.prevView = S.view; S.view = 'nearfar'; render();
    };
    if (!navigator.geolocation) return centre();
    say('Finding your location.');
    navigator.geolocation.getCurrentPosition(check, centre, { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 });
  }
  function viewNearFar() {
    const c = S.nearCity;
    show(c ? '<h2 id="h-far" tabindex="-1">You are far from ' + esc(cityName(S.region)) + '. Switch to ' + esc(cityName(c)) + '?</h2><div class="stack"><button type="button" class="btn btn-primary" data-switch-near="' + c + '">' + icon('check') + '<span>Switch to ' + esc(cityName(c)) + '</span></button><button type="button" class="btn btn-secondary" data-stay-city>Stay in ' + esc(cityName(S.region)) + '</button></div>'
      : '<h2 id="h-far" tabindex="-1">You are outside our cities.</h2><p class="muted">Near me works inside a covered city.</p><div class="stack"><button type="button" class="btn btn-primary" data-choose-city>' + icon('list') + '<span>Choose a city</span></button><button type="button" class="btn btn-secondary" data-stay-city>Stay in ' + esc(cityName(S.region)) + '</button></div>', { label: 'Near me', title: 'Near me' });
  }

  // ------------------------------------------------------------------ rendering and events
  function render() {
    const it = S.it;
    if (S.view === 'start') { select(null); viewStart(); }
    else if (S.view === 'results') viewResults();
    else if (S.view === 'card' && it) viewCard(it);
    else if (S.view === 'details' && it) viewDetails(it);
    else if (S.view === 'route' && it) navRender();
    else if (S.view === 'legend') viewLegend();
    else if (S.view === 'locating') viewLocating();
    else if (S.view === 'choose') viewChoose(S.chooseWhy);
    else if (S.view === 'usecity' && S.useCity) viewUseCity(S.useCity);
    else if (S.view === 'nearfar') viewNearFar();
    else if (S.view === 'saved') { syncMap(FAVS.map((id) => byId.get(id)).filter((x) => x && x.p.region === S.region)); viewSaved(); }
    else viewStart();
  }
  function toast(msg, action) { ui.toast(msg, action ? { action } : {}); }
  function shareUrl(it) { const u = new URL(location.href); u.search = ''; u.searchParams.set('region', it.p.region); u.hash = '#place=' + encodeURIComponent(it.p.link_id); return u.href; }
  function copyText(text, ok) {
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(() => toast(ok), () => toast('Copy this: ' + text));
  }
  document.addEventListener('click', (e) => {
    const t = e.target.closest('[data-back],[data-go],[data-type],[data-az],[data-open],[data-open-saved],[data-saved-filter],[data-more],[data-clear],[data-save],[data-details],[data-route],[data-more-details],[data-report],[data-copy],[data-unsave],[data-edit],[data-sketch],[data-copy-restore],[data-restore-paste],[data-restore-do],[data-restore-cancel],#back,#settings,#near');
    if (!t) return;
    const d = t.dataset;
    if (t.id === 'back' || 'back' in d) { back(); return; }
    if (t.id === 'near') { nearMe(); return; }
    if ('go' in d) { e.preventDefault(); if (d.go === 'saved') S.edit = false; go(d.go); return; }
    if ('type' in d) { S.type = S.type === d.type && S.view === 'results' ? null : d.type; S.shown = 10; S.az = false; S.near = false; S.q = ''; q.value = ''; clearSel(); go('results', { push: S.view !== 'results' }); fit(results()); return; }
    if ('az' in d) { S.az = true; S.type = null; S.q = ''; S.shown = 10; go('results'); return; }
    if ('open' in d) { const it = ITEMS[+d.open]; if (it.p.region !== S.region) { switchTo(it.p.region, { silent: true }).then(() => openPlace(it)); } else openPlace(it); return; }
    if ('openSaved' in d) { const id = d.openSaved, r = favRegion(id); switchTo(r, { silent: true }).then((ok) => { const it = byId.get(id); if (ok && it) openPlace(it); }); return; }
    if ('savedFilter' in d) { S.savedFilter = !S.savedFilter; viewSaved(); const b = $('[data-saved-filter]'); if (b) b.focus(); return; }
    if ('more' in d) { S.shown += 10; viewResults(); const rows = $('#rows'); const nxt = rows && rows.children[S.shown - 10]; if (nxt) nxt.querySelector('button').focus(); return; }
    if ('clear' in d) { S.q = ''; q.value = ''; S.type = null; S.prev = []; go('start', { push: false }); return; }
    if ('save' in d) { const it = ITEMS[+d.save], was = isFav(it); setFav(it, !was); render(); say((!was ? 'Saved ' : 'Removed ') + it.p.name + '.'); toast(!was ? 'Saved ' + it.p.name : 'Removed ' + it.p.name, was ? { label: 'Undo', onClick: () => { setFav(it, true); render(); } } : null); return; }
    if ('unsave' in d) { const it = byId.get(d.unsave), name = it ? it.p.name : (SNAP[d.unsave] || {}).n || 'place'; const snap = SNAP[d.unsave]; FAVS = FAVS.filter((x) => x !== d.unsave); delete SNAP[d.unsave]; bumpChanges(); persist(); refreshPins(); render(); toast('Removed ' + name, { label: 'Undo', onClick: () => { FAVS.push(d.unsave); if (snap) SNAP[d.unsave] = snap; persist(); refreshPins(); render(); } }); return; }
    if ('details' in d) { S.it = ITEMS[+d.details]; S.more = false; go('details'); return; }
    if ('moreDetails' in d) { S.more = !S.more; viewDetails(S.it); const b = $('[data-more-details]'); if (b) b.focus(); return; }
    if ('route' in d) { navOpen(ITEMS[+d.route]); return; }
    if ('report' in d) { atlas.emit('atlas:open-report', { placeId: ITEMS[+d.report].p.link_id, region: ITEMS[+d.report].p.region }); return; }
    if ('copy' in d) { const it = ITEMS[+d.copy]; copyText(shareUrl(it), 'Link copied.'); return; }
    if ('edit' in d) { S.edit = !S.edit; viewSaved(); const b = $('[data-edit]'); if (b) b.focus(); return; }
    if ('sketch' in d) { const list = FAVS.map((id) => byId.get(id)).filter(Boolean); if (list.length) { fit(list, 16); say('Showing your saved places on the map.'); } return; }
    if ('copyRestore' in d) { store.set(LINK_KEY, JSON.stringify({ t: Date.now(), c: 0 })); copyText(restoreLink(), 'Restore link copied.'); viewSaved(); return; }
    if ('restorePaste' in d) { const ids = parseRestore($('#rl').value); if (!ids || !ids.length) { toast('That link has no saved places.'); return; } S.prev.push({ view: 'saved' }); S.view = 'restore'; viewRestore(ids); return; }
    if ('restoreCancel' in d) { S.restore = null; history.replaceState(null, '', location.pathname + location.search); back(); return; }
    if ('restoreDo' in d) { const r = S.restore; if (!r) return; const mode = $('[role=radio][aria-checked=true]').dataset.value; const next = mode === 'replace' ? [] : FAVS.slice(); r.ids.forEach((id) => { if (!next.includes(id)) { next.push(id); SNAP[id] = snapOf(byId.get(id)); } }); if (mode === 'replace') SNAP = Object.fromEntries(next.map((id) => [id, SNAP[id] || snapOf(byId.get(id))])); const before = FAVS.length; FAVS = next; persist(); refreshPins(); history.replaceState(null, '', location.pathname + location.search); S.restore = null; S.prev = []; S.view = 'saved'; render(); toast('Restored ' + Math.max(0, FAVS.length - before) + ' place' + (FAVS.length - before === 1 ? '' : 's') + '.'); return; }
  });
  document.addEventListener('atlas:open-saved', () => { S.edit = false; if (S.view !== 'saved') go('saved'); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !document.querySelector('.sheet.modal') && S.view !== 'start' && document.activeElement !== q && body.contains(document.activeElement)) { back(); } });
  $('#legend-open') && ($('#legend-open').onclick = () => go('legend'));
  $('#asof').textContent = asOf;

  // ------------------------------------------------------------------ start
  function openFromHash(initial) {
    const h = location.hash;
    let m = /^#place=(.+)$/.exec(h);
    if (m) { const it = byId.get(decodeURIComponent(m[1])); if (it) { S.prev = []; if (it.p.region !== S.region) switchTo(it.p.region, { save: false, silent: true, url: false }).then(() => openPlace(it, { details: true })); else openPlace(it, { details: true }); } return; }
    if (h === '#saved' && initial === true) { S.prev = []; S.edit = false; go('saved', { push: false }); return; }   // the Saved tab of the other pages links here
    m = /^#saved=(.*)$/.exec(h);
    if (m) { const ids = parseRestore(h); if (ids && ids.length) { S.prev = [{ view: 'start' }]; S.view = 'restore'; viewRestore(ids); } }
  }
  window.addEventListener('hashchange', () => openFromHash());
  window.AtlasMap = { S, ITEMS, map, openPlace, go, results, openNow, nearMe, REG, CATALOG, switchTo, cityName };
  updateCityButtons();
  bootRegion().then(() => openFromHash(true));
  document.documentElement.setAttribute('data-map-ready', '1');
})();
