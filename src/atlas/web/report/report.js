/* Rate or report (session B2): the one-screen form, built on the B0 foundation. Plain ES2019.
   Needs: window.__RATECFG {url, key} (public Supabase values) or null; atlas events and atlas.ui from the foundation.
   Optional: window.__MAPDATA (places for "Change place"), window.atlasRegion() (the region the page is showing).
   Opens from the event atlas:open-report {placeId, region}. Two separate calls: submit_rating and submit_problem_report;
   a part that saved is never sent again. Everything that is kept stays in this browser: draft, ids, "my reports". */
(function () {
  'use strict';
  const CFG = window.__RATECFG || null, ui = atlas.ui, icon = ui.icon, esc = ui.esc;
  const $ = (s, r) => (r || document).querySelector(s);
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); return true; } catch (e) { return false; } },
  };
  const json = (k, d) => { try { return JSON.parse(store.get(k)) || d; } catch (e) { return d; } };
  const newId = () => (crypto.randomUUID ? crypto.randomUUID() : '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, (c) => (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)));
  let DEVICE = store.get('atlas-device');
  if (!DEVICE) { DEVICE = newId(); store.set('atlas-device', DEVICE); }
  const RATING_REGIONS = ['cincinnati', 'oxford'];   // ratings.sql allows only these (owner decision: not widened yet)
  const CITY = {};   // short city names come from the catalog of cities the page was built with
  (window.__REGIONS || []).forEach((r) => { CITY[r.id] = r.short; });
  const STAR_WORDS = ['', 'Not accessible', 'Hard to use', 'Usable with effort', 'Mostly accessible', 'Fully accessible'];
  const PARTS = [['entrance', 'Entrance'], ['restroom', 'Restroom'], ['parking', 'Parking'], ['inside', 'Inside']];
  const WHO = [['wheelchair', 'Wheelchair'], ['mobility_aid', 'Cane or walker'], ['blind_low_vision', 'Blind or low vision'], ['deaf_hoh', 'Deaf or hard of hearing'], ['companion', 'Companion'], ['other', 'Other']];
  // chip -> database category (Blocked and Broken lift both send blocked_or_broken)
  const PROBLEMS = [['blocked', 'Blocked', 'blocked_or_broken', 'alert'], ['lift', 'Broken lift', 'blocked_or_broken', 'door'], ['wrong', 'Wrong info', 'wrong_info', 'info'], ['other', 'Other', 'other', 'plus']];
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const BADGE = { accessible: 'yes', partial: 'partial', not_accessible: 'no', unknown: 'unknown' };
  const WORD = { yes: 'Accessible', partial: 'Partly accessible', no: 'Not accessible', unknown: 'Not known' };
  const LAYER = { culture: 'Museum', park: 'Park', restroom: 'Restroom', adaptive_recreation: 'Recreation', lodging: 'Lodging', event: 'Event venue', building: 'Building', food_drink: 'Food and drink', service: 'Shop', trail: 'Trail' };

  // ---- places for "Change place"
  const PLACES = [];
  for (const region of Object.keys(window.__MAPDATA || {})) {
    for (const f of window.__MAPDATA[region].features) {
      const p = f.properties;
      if (p.layer === 'event') continue;
      const c = f.geometry.type === 'Point' ? [f.geometry.coordinates[1], f.geometry.coordinates[0]] : null;
      PLACES.push({ id: p.link_id, name: p.name, region: p.region || region, rating: BADGE[p.access_rating] || 'unknown', layer: LAYER[p.layer] || 'Place', pt: c });
    }
  }
  const placeById = (id) => PLACES.find((p) => p.id === id) || null;
  // pages without the map's data (the chat page) hand over their places after they load
  function setPlaces(list) { PLACES.length = 0; list.forEach((p) => PLACES.push(p)); }
  const currentRegion = () => (window.atlasRegion && window.atlasRegion()) || Object.keys(window.__MAPDATA || {})[0] || null;

  // ---- state
  let R = null, root = null, opener = null, lastTab = null, held = [];
  const fresh = () => ({ view: 'form', place: null, noPlace: false, stars: 0, parts: {}, visit: '', who: '', problem: '', comment: '', contact: '', photo: null, photoUrl: null, photoMsg: '', photoErr: '', openMore: false, openExtra: false, errors: [], banner: null, busy: false, sent: { rating: false, problem: false }, ids: { problem: newId() }, ref: null, limit: { rating: false, problem: false }, existing: null, outcome: null, prev: 'form', deleted: false });
  const draftKey = () => 'atlas-report-draft-v2-' + (R.noPlace ? 'map' : R.place ? R.place.id : 'none');
  const saveDraft = () => store.set(draftKey(), JSON.stringify({ stars: R.stars, parts: R.parts, visit: R.visit, who: R.who, problem: R.problem, comment: R.comment, contact: R.contact, pid: R.ids.problem }));
  const rated = (id) => json('atlas-rated-' + id, null);
  const mine = () => json('atlas-my-reports', []);
  const setMine = (l) => store.set('atlas-my-reports', JSON.stringify(l.slice(0, 100)));
  const rateable = () => !R.noPlace && R.place && RATING_REGIONS.includes(R.place.region);
  const region = () => (R.place ? R.place.region : currentRegion());
  const wantRating = () => rateable() && R.stars > 0 && !R.sent.rating && !R.limit.rating;
  const wantProblem = () => !!R.problem && !R.sent.problem;
  const limit = () => (R.stars > 0 ? 500 : 1000);

  // ---- open and close
  function open(ctx, op) {
    if (root) return;
    opener = op || document.activeElement;
    R = fresh();
    const place = ctx && ctx.placeId ? placeById(ctx.placeId) : null;
    if (place) R.place = place;
    else if (ctx && ctx.text && !ctx.placeId) R.noPlace = true;   // a problem with an answer is about the assistant, not one place
    else if (ctx && ctx.placeId) R.place = { id: ctx.placeId, name: 'this place', region: ctx.region || currentRegion(), rating: 'unknown', layer: 'Place' };
    else R.noPlace = false;
    const ex = R.place && rated(R.place.id);
    if (ex && ex.overall) { R.existing = ex; R.stars = ex.overall; R.parts = { entrance: ex.entrance, restroom: ex.restroom, parking: ex.parking, inside: ex.inside }; R.visit = ex.visited || ''; R.who = ex.profile || ''; R.comment = ex.comment || ''; R.banner = { kind: 'info', icon: 'check', text: 'You rated this place ' + ex.overall + ' of 5. You can change it.' }; }
    const d = json(draftKey(), null);
    if (d && !ex) { R.stars = d.stars || 0; R.parts = d.parts || {}; R.visit = d.visit || ''; R.who = d.who || ''; R.problem = d.problem || ''; R.comment = d.comment || ''; R.contact = d.contact || ''; if (d.pid) R.ids.problem = d.pid; R.openMore = Object.values(R.parts).some(Boolean) || !!R.visit || !!R.who; R.openExtra = !!(R.comment || R.contact); }
    else if (d && ex) { R.problem = d.problem || ''; R.contact = d.contact || ''; if (d.pid) R.ids.problem = d.pid; }
    if (ctx && ctx.text) { R.comment = String(ctx.text).slice(0, 500); R.openExtra = true; }
    if (ctx && ctx.stars >= 1 && ctx.stars <= 5 && !ex) R.stars = ctx.stars | 0;                       // from the stars on the place card
    if (ctx && ctx.problem && PROBLEMS.some((p) => p[0] === ctx.problem)) R.problem = ctx.problem;     // from a problem chip on the place card
    const sent = mine().find((m) => m.k === 'problem' && m.id === R.ids.problem);
    if (sent) { R.sent.problem = true; R.ref = sent.ref; R.banner = { kind: 'info', icon: 'check', text: 'Already sent. Your code is ' + sent.ref + '.', action: ['See my report', 'mine'] }; }
    root = document.createElement('div');
    root.className = 'ax rp';
    root.setAttribute('role', 'dialog'); root.setAttribute('aria-modal', 'true'); root.setAttribute('aria-labelledby', 'rp-title');
    document.body.appendChild(root);
    held = [];
    // a page can name what to freeze with data-rp-inert (the chat page keeps its tab bar usable); else every other child of <body>
    const marked = [...document.querySelectorAll('[data-rp-inert]')];
    (marked.length ? marked : [...document.body.children].filter((c) => c !== root && !c.classList.contains('only-phone') && !c.classList.contains('portal') && c.id !== 'live' && c.tagName !== 'SCRIPT')).forEach((c) => { if (!c.inert) { c.inert = true; held.push(c); } });
    lastTab = $('.tabbar .tab[aria-current="page"]');
    ui.setTab('report');
    document.addEventListener('keydown', onKey, true);
    render(null, true);
    probe();
  }
  function close(opts) {
    if (!root) return;
    document.removeEventListener('keydown', onKey, true);
    if (R.photoUrl) URL.revokeObjectURL(R.photoUrl);
    root.remove(); root = null;
    held.forEach((c) => { c.inert = false; }); held = [];
    ui.setTab(lastTab ? lastTab.getAttribute('data-tab') : 'map');
    if (!(opts && opts.noFocus) && opener && document.contains(opener)) opener.focus();
    R = null;
  }
  function onKey(e) {
    if (document.querySelector('.sheet.modal')) return;   // a sheet on top handles its own keys
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (e.key !== 'Tab' || !root) return;
    const f = [...root.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]):not([type=hidden]):not(.rp-hp *),select:not([disabled]),textarea:not([disabled]),summary')].filter((n) => n.offsetParent !== null && !n.closest('.rp-hp'));
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (!root.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
    else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  let probed = null;
  async function probe() {
    if (probed === true) return;
    const at = +(store.get('atlas-report-ok') || 0);
    if (at && Date.now() - at < 600000) { probed = true; return; }
    try { const r = await fetch(CFG.url + '/rest/v1/rpc/report_ping', { method: 'POST', headers: hdr({ 'Content-Type': 'application/json' }), body: '{}' }); probed = r.ok; if (r.ok) store.set('atlas-report-ok', String(Date.now())); } catch (e) { probed = null; }
    if (probed === false && R) { R.banner = { kind: 'warn', icon: 'alert', text: 'Reporting is not available right now. Please try again later.' }; render(); }
  }
  const hdr = (extra) => Object.assign({ apikey: CFG.key }, CFG.key.startsWith('eyJ') ? { Authorization: 'Bearer ' + CFG.key } : {}, extra || {});

  // ---- rendering
  const starsHtml = () => {
    const off = R.limit.rating;
    return '<fieldset class="group" id="rp-stars"' + (off ? ' disabled' : '') + ' aria-describedby="rp-stars-err" aria-labelledby="rp-stars-l"><div class="rate-row"><span class="h2s" id="rp-stars-l">How accessible was it?</span><div class="stars">'
      + [1, 2, 3, 4, 5].map((n) => '<label class="star"><input type="radio" name="rp-star" value="' + n + '" aria-label="' + n + ' of 5, ' + STAR_WORDS[n] + '"' + (R.stars === n ? ' checked' : '') + '>' + icon('star') + '<span class="n" aria-hidden="true">' + n + '</span></label>').join('')
      + '</div></div><p class="starword" id="rp-starword" aria-live="polite">' + (R.stars ? R.stars + ' of 5, ' + STAR_WORDS[R.stars] : '') + (R.sent.rating ? ' <span class="saved">' + icon('check') + 'Saved</span>' : '') + '</p>'
      + errFor('stars') + '</fieldset>';
  };
  const errFor = (k) => { const e = R.errors.find((x) => x[0] === k); return '<p class="err" id="rp-' + k + '-err"' + (e ? '' : ' hidden') + '>' + icon('alert') + '<span>' + (e ? esc(e[1]) : '') + '</span></p>'; };
  const chip = (attrs, ic, label, on) => '<button type="button" class="chip" ' + attrs + ' aria-pressed="' + !!on + '">' + icon('check', 'tick') + (ic ? icon(ic) : '') + '<span>' + label + '</span></button>';
  function moreHtml() {
    const months = []; const now = new Date();
    for (let i = 0; i < 12; i++) { const d = new Date(now.getFullYear(), now.getMonth() - i, 1); months.push([d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-01', MON[d.getMonth()] + ' ' + d.getFullYear()]); }
    return '<details class="disc rp-more" id="rp-more"' + (R.openMore ? ' open' : '') + '><summary><span><b>Rate more</b><small>Entrance, restroom, parking, inside</small></span>' + icon('down') + '</summary><div class="body">'
      + '<p class="hint">Tap any. Skip what you did not use.</p>'
      + PARTS.map(([k, l]) => '<div class="part" role="group" aria-label="' + l + '"><span>' + l + '</span>' + chip('data-part="' + k + '" data-v="5"', null, 'Good', R.parts[k] === 5).replace('<span>Good</span>', '<span>Good<span class="vh"> ' + l.toLowerCase() + '</span></span>') + chip('data-part="' + k + '" data-v="1"', 'no', 'Hard', R.parts[k] === 1).replace('<span>Hard</span>', '<span>Hard<span class="vh"> ' + l.toLowerCase() + '</span></span>') + '</div>').join('')
      + '<div class="field"><label for="rp-visit" class="lbl">Visit month</label><select class="select" id="rp-visit"><option value="">Not sure</option>' + months.map(([v, t]) => '<option value="' + v + '"' + (R.visit === v ? ' selected' : '') + '>' + t + '</option>').join('') + '</select></div>'
      + '<div class="stack"><span class="lbl" id="rp-who-l">I use</span><div class="chip-wrap" role="group" aria-labelledby="rp-who-l">' + WHO.map(([k, l]) => chip('data-who="' + k + '"', null, l, R.who === k)).join('') + '</div></div></div></details>';
  }
  function extraHtml() {
    const over = R.comment.length > limit();
    const photoPart = '<div class="field"><span class="lbl" id="rp-photo-l">Photo <span class="tag">Problem only</span></span>'
      + '<div class="rowbtns" role="group" aria-labelledby="rp-photo-l">' + (matchMedia('(pointer:coarse)').matches ? '<button type="button" class="btn btn-secondary" data-cam>' + icon('camera') + '<span>Take photo</span></button>' : '') + '<button type="button" class="btn btn-secondary" data-pick>' + icon('image') + '<span>Choose photo</span></button></div>'
      + '<input type="file" accept="image/*" capture="environment" id="rp-cam" hidden><input type="file" accept="image/*" id="rp-file" hidden>'
      + '<p class="hint" id="rp-photo-hint">Goes with a problem. Shrinks to about 200 KB. No location data.</p>'
      + (R.photoErr ? '<p class="err" id="rp-photo-err">' + icon('alert') + '<span>' + esc(R.photoErr) + '</span></p>' : errFor('photo'))
      + (R.photo ? '<div class="photo-prev"><div class="thumb"><img alt="Preview of the photo you added" src="' + R.photoUrl + '" style="width:56px;height:56px;object-fit:cover;border-radius:10px"></div><div style="flex:1"><b>Photo ready</b><div class="muted small">' + Math.round(R.photo.size / 1024) + ' KB</div></div><button type="button" class="btn btn-secondary" data-rm>' + icon('trash') + '<span>Remove</span></button></div>' : '')
      + '<p class="small muted" id="rp-pmsg" role="status" aria-live="polite">' + esc(R.photoMsg) + '</p></div>';
    return '<details class="disc rp-more" id="rp-extra"' + (R.openExtra ? ' open' : '') + '><summary><span><b>Add photo or comment</b></span>' + icon('down') + '</summary><div class="body">'
      + '<div class="field"><label class="lbl" for="rp-comment">Comment <span class="tag">Optional</span></label><textarea class="textarea" id="rp-comment" rows="3" aria-describedby="rp-comment-hint rp-comment-err"' + (over ? ' aria-invalid="true"' : '') + '>' + esc(R.comment) + '</textarea>'
      + '<div class="hint rp-hint-row"><span id="rp-comment-hint">Saved with your rating or report. Not published.</span><span id="rp-count" aria-live="off">' + R.comment.length + ' of ' + limit() + '</span></div>'
      + errFor('comment') + '</div>' + photoPart
      + '<div class="field"><label class="lbl" for="rp-contact">Want a reply? <span class="tag">Problem only</span></label><input class="input" id="rp-contact" maxlength="200" autocomplete="off" placeholder="Email or phone" value="' + esc(R.contact) + '"></div>'
      + '<div class="rp-hp vh" aria-hidden="true"><label>Website<input type="text" id="rp-web" tabindex="-1" autocomplete="off"></label></div></div></details>';
  }
  function placeRow() {
    if (R.noPlace) return '<div class="rp-place" id="rp-place"><span>About: <b>the map, not one place</b></span><button type="button" class="btn btn-ghost" data-change>Change</button></div>';
    if (!R.place) return '<div class="rp-place" id="rp-place">' + icon('map') + '<span class="muted">No place yet</span><button type="button" class="btn btn-secondary" data-change>Choose place</button></div>' + errFor('place');
    return '<div class="rp-place" id="rp-place"><button type="button" class="rp-picker" data-change aria-label="Change place, now ' + esc(R.place.name) + '">' + icon('pin') + '<span class="n">' + esc(R.place.name) + '</span>' + icon('down') + '</button></div>' + errFor('place');
  }
  function bannerHtml() {
    const parts = [];
    if (R.errors.length) {
      parts.push('<div class="banner errsum" id="rp-errsum" tabindex="-1" aria-labelledby="rp-errsum-h">' + icon('alert') + '<div><b id="rp-errsum-h">Fix ' + R.errors.length + ' thing' + (R.errors.length > 1 ? 's' : '') + ' to send</b><ul>' + R.errors.map((e) => '<li><a href="#" data-fix="' + e[0] + '">' + esc(e[2] || e[1]) + '</a></li>').join('') + '</ul></div></div>');
    }
    if (R.banner) { const b = R.banner; parts.push('<div class="banner ' + (b.kind === 'info' ? 'info' : b.kind === 'error' ? 'errsum' : '') + '" role="status">' + icon(b.icon || 'alert') + '<span>' + esc(b.text) + '</span>' + (b.action ? '<button type="button" class="btn btn-secondary" data-act="' + b.action[1] + '">' + esc(b.action[0]) + '</button>' : '') + '</div>'); }
    return parts.join('');
  }
  function sendLabel() {
    if (R.busy) return 'Sending';
    if (R.banner && (R.banner.kind === 'error' || R.banner.tryAgain)) return 'Try again';
    if (R.sent.problem && !wantRating() && !wantProblem()) return 'See my report';
    const r = wantRating() || (R.stars > 0 && !R.place && !R.noPlace && !R.sent.rating), p = wantProblem();
    return r && p ? 'Send both' : p ? 'Send report' : r ? (R.existing || R.sent.rating ? 'Update rating' : 'Send rating') : 'Send';
  }
  function formHtml() {
    const rateOk = rateable();
    return placeRow() + bannerHtml()
      + (R.noPlace ? '' : rateOk ? starsHtml() + moreHtml() : (R.place ? '<div class="banner info" role="note">' + icon('info') + '<span>Ratings are not open for ' + esc(CITY[R.place.region] || R.place.region) + ' yet. You can still report a problem.</span></div>' : starsHtml() + moreHtml()))
      + '<fieldset class="group" id="rp-problem"' + (R.limit.problem ? ' disabled' : '') + ' aria-describedby="rp-problem-err"><legend class="h2s">Something is wrong? <span class="tag">Optional</span></legend><div class="chip-grid">'
      + PROBLEMS.map(([k, l, c, ic]) => chip('data-problem="' + k + '"', ic, l, R.problem === k)).join('') + '</div>' + errFor('problem') + '</fieldset>'
      + extraHtml()
      + '<p><button type="button" class="btn btn-ghost" data-act="mine">' + icon('list') + '<span>My ratings and reports on this device</span></button></p>';
  }
  const fmtDate = (t) => { const d = new Date(t), n = new Date(); return d.toDateString() === n.toDateString() ? 'today' : d.getDate() + ' ' + MON[d.getMonth()]; };
  function minesHtml() {
    const l = mine();
    return '<div class="banner info" role="note">' + icon('alert') + '<span>This list is only on this device. Clearing browser data removes it.</span></div>'
      + (l.length ? '<ul class="plain">' + l.map((m) => m.k === 'rating'
        ? '<li class="mine"><span class="tile-ic">' + icon('star') + '</span><div><b>Rating: ' + m.stars + ' of 5</b><div class="muted small">' + esc(m.name) + '</div><div class="muted small">Sent ' + fmtDate(m.ts) + '</div></div><button type="button" class="btn btn-secondary" data-change-rating="' + esc(m.id) + '">Change<span class="vh"> rating for ' + esc(m.name) + '</span></button></li>'
        : '<li class="mine"><span class="tile-ic">' + icon('alert') + '</span><div><b>Problem: ' + esc(m.label) + '</b><div class="muted small">' + esc(m.name || 'The map') + '</div><div class="muted small">Sent ' + fmtDate(m.ts) + ' · Code ' + esc(m.ref) + (m.photo ? ' · Photo' : '') + '</div></div><button type="button" class="btn btn-danger" data-del="' + esc(m.id) + '">' + icon('trash') + '<span>Delete<span class="vh"> problem ' + esc(m.ref) + '</span></span></button></li>').join('') + '</ul>'
        : '<div class="state"><span class="big">' + icon('list') + '</span><p class="lead">Nothing here yet</p><p class="muted">Ratings and problems you send from this device show up here.</p></div>')
      + '<p class="muted small">Problems are kept up to 24 months. Delete removes the text and photo. A rating can be changed, not deleted.</p>';
  }
  function doneHtml() {
    const o = R.outcome, name = R.place ? R.place.name : 'the map';
    const sub = o.rating && o.problem ? 'Rating saved. Problem sent. Code <b>' + esc(R.ref) + '</b>' : o.rating ? 'Your rating is saved.' : 'Your code is <b>' + esc(R.ref) + '</b>';
    const tl = [];
    if (o.rating) tl.push(['check', 'Rating saved', o.stars + ' of 5 · ' + name]);
    if (o.problem) tl.push(['check', 'Problem sent', o.label + ' · code ' + R.ref]);
    tl.push(o.problem ? ['clock', 'The team reads it', 'No update shows here'] : ['map', 'Counts in the visitor average', 'Comments are never published']);
    if (o.problem) tl.push(['map', 'The place is checked', 'The map may change later']);
    return '<div class="done"><span class="bigcheck">' + icon('check') + '</span><h2 id="rp-done-h" tabindex="-1" class="h1">Thank you</h2><p class="muted">' + sub + '</p>'
      + '<ol class="timeline">' + tl.map(([ic, a, b]) => '<li>' + icon(ic) + '<div><b>' + esc(a) + '</b><div class="muted small">' + esc(b) + '</div></div></li>').join('') + '</ol>'
      + '<button type="button" class="btn btn-primary block" data-act="again">' + icon('plus') + '<span>' + (o.problem ? 'Report another' : 'Rate another') + '</span></button>'
      + (o.problem ? '<button type="button" class="btn btn-secondary block" data-act="done">Done</button>' : '<button type="button" class="btn btn-secondary block" data-act="again-place">' + icon('report') + '<span>Report a problem here</span></button>')
      + '<div class="rowbtns" style="justify-content:center">' + (o.rating ? '<button type="button" class="btn btn-ghost" data-act="change">Change rating</button>' : '') + (o.problem ? '<button type="button" class="btn btn-danger" data-del="' + esc(R.ids.problem) + '">' + icon('trash') + '<span>Delete report</span></button>' : '') + '</div></div>';
  }
  function render(focus, first) {
    if (!root) return;
    const scrollTop = (root.querySelector('.rp-scroll') || {}).scrollTop || 0;
    const titles = { form: 'Rate or report', done: 'Sent', mine: 'My ratings and reports', deleted: 'Report deleted' };
    const view = R.view;
    const send = '<button type="submit" class="btn btn-primary block" id="rp-send"' + (R.busy ? ' aria-busy="true" disabled' : '') + '>' + icon(R.busy ? 'spinner' : 'send', R.busy ? 'spin' : '') + '<span>' + sendLabel() + '</span></button>';
    root.innerHTML = '<header class="appbar"><button type="button" class="btn btn-icon btn-ghost" data-act="back" aria-label="' + (view === 'form' ? 'Back' : 'Back to the form') + '">' + icon('back') + '</button><h1 class="title" id="rp-title" tabindex="-1">' + titles[view] + '</h1><button type="button" class="btn btn-icon btn-ghost" data-act="close" aria-label="Close">' + icon('close') + '</button></header>'
      + '<form class="rp-form" novalidate><div class="rp-scroll">'
      + (view === 'form' ? formHtml() : view === 'mine' ? minesHtml() : view === 'done' ? doneHtml() : '<div class="done"><span class="bigcheck off">' + icon('trash') + '</span><h2 id="rp-done-h" tabindex="-1" class="h1">Report deleted</h2><p class="muted">The text and photo are gone.</p><button type="button" class="btn btn-primary block" data-act="again">' + icon('plus') + '<span>Report another</span></button><button type="button" class="btn btn-secondary block" data-act="done">Done</button></div>')
      + '</div>'
      + (view === 'form' ? '<div class="rp-foot">' + (R.busy ? '<p class="small muted" role="status" aria-live="polite">' + icon('spinner', 'spin') + ' Sending your ' + (wantRating() && wantProblem() ? 'rating and report' : wantRating() ? 'rating' : 'report') + '</p>' : '') + '<p class="rp-priv">' + icon('yes') + '<span>No name needed. We keep your report, device type and page address. <button type="button" class="link" data-act="keep">What we keep</button></span></p>' + send + '</div>' : view === 'mine' ? '<div class="rp-foot"><button type="button" class="btn btn-primary block" data-act="form">' + icon('report') + '<span>Rate or report</span></button></div>' : '')
      + '</form>';
    const sc = root.querySelector('.rp-scroll'); sc.scrollTop = first ? 0 : scrollTop;
    if (focus) { const el = typeof focus === 'string' ? $(focus, root) : focus; if (el) { el.focus({ preventScroll: true }); if (focus === '#rp-errsum') sc.scrollTop = 0; } }
    else if (first || view !== 'form') { const h = $('#rp-done-h', root) || $('#rp-title', root); if (h) h.focus({ preventScroll: true }); }
  }

  // ---- changing things
  function setBanner(b) { R.banner = b; }
  function validate() {
    const errs = [];
    if (!R.noPlace && !R.place) errs.push(['place', 'Choose a place, or use Not about one place.', 'Choose a place']);
    if (!R.stars && !R.problem) errs.push(['stars', 'Rate it or choose a problem.', 'Choose stars or a problem']);
    if (R.stars && R.place && !rateable() && !R.problem) errs.push(['problem', 'Ratings are not open for this city yet. Choose a problem to report.', 'Choose a problem']);
    if (R.comment.length > limit()) { const n = R.comment.length - limit(); errs.push(['comment', R.comment.length + ' of ' + limit() + '. Remove ' + n + ' characters.', 'Shorten the comment by ' + n + ' characters']); }
    if (R.photo && !R.problem) errs.push(['photo', 'A photo goes with a problem. Choose one above, or remove the photo.', 'A photo needs a problem']);
    return errs;
  }
  async function shrinkPhoto(file) {
    if (!/^image\//.test(file.type) && !/\.(jpe?g|png|webp|gif|heic|heif)$/i.test(file.name)) throw new Error('That file is not a photo.');
    let bmp;
    try { bmp = await createImageBitmap(file, { imageOrientation: 'from-image' }); }
    catch (e) { bmp = await new Promise((ok, no) => { const im = new Image(); im.onload = () => ok(im); im.onerror = () => no(new Error('This photo format cannot be used here. Try a JPEG or PNG, or take a new photo.')); im.src = URL.createObjectURL(file); }); }
    const W = bmp.width || bmp.naturalWidth, H = bmp.height || bmp.naturalHeight;
    for (const max of [1280, 960, 720]) {
      const k = Math.min(1, max / Math.max(W, H)), cv = document.createElement('canvas');
      cv.width = Math.max(1, Math.round(W * k)); cv.height = Math.max(1, Math.round(H * k));
      const g = cv.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, cv.width, cv.height); g.drawImage(bmp, 0, 0, cv.width, cv.height);
      for (const q of [0.75, 0.6, 0.45, 0.35]) {   // re-encoding drops every kind of metadata, including GPS position
        const blob = await new Promise((r) => cv.toBlob(r, 'image/jpeg', q));
        if (blob && blob.size <= 200000) return blob;
      }
    }
    throw new Error('Photo too large. Try a smaller one.');
  }
  const b64 = (blob) => new Promise((ok, no) => { const f = new FileReader(); f.onload = () => ok(String(f.result).split(',')[1]); f.onerror = no; f.readAsDataURL(blob); });
  async function takePhoto(file) {
    if (!file) return;
    R.photoErr = ''; R.photoMsg = 'Preparing your photo…'; const t = $('#rp-pmsg', root); if (t) t.textContent = R.photoMsg;
    try { const blob = await shrinkPhoto(file); if (R.photoUrl) URL.revokeObjectURL(R.photoUrl); R.photo = blob; R.photoUrl = URL.createObjectURL(blob); R.photoMsg = 'Photo added.'; R.openExtra = true; }
    catch (e) { R.photoMsg = ''; R.photoErr = e.message || 'The photo could not be used.'; R.openExtra = true; }
    render('#rp-photo-hint');
  }

  // ---- sending (two calls; what saved is never sent again)
  const rpc = (name, body) => fetch(CFG.url + '/rest/v1/rpc/' + name, { method: 'POST', headers: hdr({ 'Content-Type': 'application/json' }), body: JSON.stringify(body) });
  async function readError(r) { let t = ''; try { t = (await r.json()).message || ''; } catch (x) { /* not json */ } return t || 'the server said ' + r.status; }
  async function sendRating() {
    const body = { p_link_id: R.place.id, p_region: R.place.region, p_device_id: DEVICE, p_overall: R.stars, p_entrance: R.parts.entrance || null, p_restroom: R.parts.restroom || null, p_parking: R.parts.parking || null, p_inside: R.parts.inside || null, p_profile: R.who || null, p_visited: R.visit || null, p_comment: R.comment.trim() || null };
    const r = await rpc('submit_rating', body);
    if (!r.ok) throw new Error(await readError(r));
    store.set('atlas-rated-' + R.place.id, JSON.stringify({ overall: R.stars, entrance: R.parts.entrance || null, restroom: R.parts.restroom || null, parking: R.parts.parking || null, inside: R.parts.inside || null, profile: R.who || null, visited: R.visit || null, comment: R.comment.trim() || null }));
    const l = mine().filter((m) => !(m.k === 'rating' && m.id === R.place.id)); l.unshift({ k: 'rating', id: R.place.id, name: R.place.name, region: R.place.region, stars: R.stars, ts: Date.now() }); setMine(l);
    R.sent.rating = true;
  }
  async function sendProblem() {
    const chipName = PROBLEMS.find((p) => p[0] === R.problem);
    let text = R.comment.trim();
    if (!text) text = chipName[1]; else if (text.length < 5) text = chipName[1] + ': ' + text;   // the database needs 5 to 1000 characters
    const body = { p_report_id: R.ids.problem, p_device_id: DEVICE, p_category: chipName[2], p_description: text.slice(0, 1000), p_link_id: R.place ? R.place.id : null, p_place_name: R.place ? R.place.name : null, p_region: region(), p_contact: R.contact.trim() || null, p_photo_b64: R.photo ? await b64(R.photo) : null, p_page_url: location.href.split('#')[0].slice(0, 300), p_user_agent: navigator.userAgent.slice(0, 300), p_website: ($('#rp-web', root) || {}).value || '' };
    const r = await rpc('submit_problem_report', body);
    if (!r.ok) throw new Error(await readError(r));
    R.ref = String(await r.json());
    const l = mine(); l.unshift({ k: 'problem', id: R.ids.problem, ref: R.ref, name: R.place ? R.place.name : '', label: chipName[1], photo: !!R.photo, region: region(), ts: Date.now() }); setMine(l);
    R.sent.problem = true;
    store.set(draftKey(), '');
  }
  const kindOf = (msg, offline) => offline ? 'offline' : /Too many ratings/i.test(msg) ? 'limit-rating' : /Too many reports/i.test(msg) ? 'limit-problem' : /very busy/i.test(msg) ? 'busy' : /photo is too large|photo must be/i.test(msg) ? 'photo' : 'fail';
  async function send() {
    if (R.busy) return;
    if (R.sent.problem && !wantRating() && !wantProblem() && R.banner && R.banner.action) { R.view = 'mine'; render(); return; }
    R.errors = validate(); R.banner = R.banner && R.banner.kind === 'info' && !R.banner.tryAgain ? R.banner : null;
    if (R.errors.length) { render('#rp-errsum'); return; }
    if (navigator.onLine === false) { saveDraft(); R.banner = { kind: 'info', icon: 'offline', text: 'You are offline. Your answers are saved on this device.', tryAgain: true }; render('#rp-send'); return; }
    R.busy = true; R.banner = null; render('#rp-send');
    const todo = { rating: wantRating(), problem: wantProblem() }, failed = [];
    let firstMsg = '', kind = '';
    const firstMsgOf = {};
    if (todo.rating) { try { await sendRating(); } catch (e) { failed.push('rating'); firstMsg = e.message; kind = kindOf(e.message, navigator.onLine === false || e instanceof TypeError); if (kind === 'limit-rating') R.limit.rating = true; } }
    if (todo.problem) { try { await sendProblem(); } catch (e) { failed.push('problem'); firstMsgOf.problem = e.message; if (!firstMsg) { firstMsg = e.message; kind = kindOf(e.message, navigator.onLine === false || e instanceof TypeError); } if (kindOf(e.message) === 'limit-problem') R.limit.problem = true; if (kindOf(e.message) === 'photo') R.photoErr = 'The photo was too large for the server. Remove it or try a smaller one.'; } }
    R.busy = false;
    if (failed.length) saveDraft();
    if (!failed.length) {
      store.set(draftKey(), ''); R.outcome = { rating: todo.rating, problem: todo.problem, stars: R.stars, label: (PROBLEMS.find((p) => p[0] === R.problem) || [])[1] }; R.view = 'done'; render(); say('Sent. ' + (todo.rating && todo.problem ? 'Rating saved. Problem sent.' : todo.rating ? 'Rating saved.' : 'Problem sent.')); return; }
    const savedRating = todo.rating && !failed.includes('rating'), savedProblem = todo.problem && !failed.includes('problem');
    const left = failed.includes('rating') ? 'Rating' : 'Problem';
    const probKind = failed.includes('problem') ? kindOf(firstMsgOf.problem || '', false) : '';
    if (savedRating && probKind === 'limit-problem') R.banner = { kind: 'warn', icon: 'clock', text: 'Rating saved. You sent 10 problems today, so the problem is not sent. Try again tomorrow.' };
    else if (savedRating && probKind === 'busy') R.banner = { kind: 'warn', icon: 'clock', text: 'Rating saved. The report form is very busy right now. Please try the problem again in an hour.' };
    else if (savedRating || savedProblem) R.banner = { kind: 'error', icon: 'alert', text: (savedRating ? 'Rating saved. Problem' : 'Problem sent. Rating') + ' not ' + (savedRating ? 'sent' : 'saved') + '. Try again.' };
    else if (kind === 'limit-rating') R.banner = { kind: 'warn', icon: 'clock', text: 'You rated 40 places today. Stars are back tomorrow. You can still report a problem.' };
    else if (kind === 'limit-problem') R.banner = { kind: 'warn', icon: 'clock', text: 'You sent 10 problems today. Your rating can still go.' };
    else if (kind === 'busy') R.banner = { kind: 'warn', icon: 'clock', text: 'The report form is very busy right now. Please try again in an hour. Your answers are saved.' };
    else if (kind === 'offline') R.banner = { kind: 'info', icon: 'offline', text: 'You are offline. Your answers are saved on this device.', tryAgain: true };
    else R.banner = { kind: 'error', icon: 'alert', text: 'Not sent. Your answers are saved. Try again.' };
    if (left === 'Rating' && kind === 'limit-rating' && todo.problem && savedProblem) R.banner = { kind: 'warn', icon: 'clock', text: 'Problem sent. You rated 40 places today, so the stars are not saved. They are back tomorrow.' };
    render('#rp-send'); say(R.banner.text);
  }
  function say(t) { const l = $('#live') || $('#ch-live'); if (!l) return; l.textContent = ''; setTimeout(() => { l.textContent = t; }, 30); }

  // ---- change place sheet
  function placeSheet() {
    let here = null, status = '', q = '', pick = R.noPlace ? '__none' : R.place ? R.place.id : '', sheet;
    const dist = (a, b) => { const r = Math.PI / 180, dLa = (b[0] - a[0]) * r, dLo = (b[1] - a[1]) * r, h = Math.sin(dLa / 2) ** 2 + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLo / 2) ** 2; return 12742000 * Math.asin(Math.sqrt(h)); };
    const fmt = (m) => (m < 300 ? Math.max(50, Math.round(m * 3.28084 / 50) * 50) + ' ft' : (m / 1609.34).toFixed(1) + ' mi');
    const node = document.createElement('div'); node.className = 'stack3';
    const list = () => {
      let l = PLACES.slice();
      const t = q.trim().toLowerCase();
      if (t) l = l.filter((p) => p.name.toLowerCase().includes(t) || p.layer.toLowerCase().includes(t));
      if (here) { l.forEach((p) => { p.d = p.pt ? dist(here, p.pt) : 1e9; }); l.sort((a, b) => a.d - b.d); } else l.sort((a, b) => a.name.localeCompare(b.name));
      return l.slice(0, 80);
    };
    const draw = () => {
      const l = list(), keep = $('.pl-list', node), top = keep ? keep.scrollTop : 0;
      node.innerHTML = (status ? '<div class="banner ' + (status.kind || '') + '" role="status">' + icon(status.icon) + '<span>' + esc(status.text) + '</span></div>' : '')
        + '<div class="pq-row"><div class="search" role="search" aria-label="Search a place">' + icon('search') + '<input type="search" id="rp-pq" value="' + esc(q) + '" placeholder="Search a place" aria-label="Search a place" autocomplete="off"></div>'
        + '<button type="button" class="btn btn-secondary" data-near aria-label="Near me">' + icon('near') + '<span>Near me</span></button></div>'
        + '<div class="pl-list" role="radiogroup" aria-label="' + (here ? 'Near you' : q ? 'Results' : 'Places') + '">' + '<button type="button" class="listrow' + (pick === '__none' ? ' sel' : '') + '" role="radio" aria-checked="' + (pick === '__none') + '" data-pid="__none"><span class="nm">Not about one place</span><span class="sub">Problem only</span></button>' + l.map((p) => '<button type="button" class="listrow' + (pick === p.id ? ' sel' : '') + '" role="radio" aria-checked="' + (pick === p.id) + '" data-pid="' + esc(p.id) + '"><span class="nm">' + esc(p.name) + '</span><span class="sub">' + esc(p.layer + (here && p.d < 1e8 ? ', ' + fmt(p.d) : '')) + '</span></button>').join('') + '</div>'
        + '<button type="button" class="btn btn-primary block" data-use>Use this place</button>';
      const nl = $('.pl-list', node); if (nl) nl.scrollTop = top;
    };
    draw();
    sheet = ui.sheet.open({ title: 'Change place', node });
    const redraw = (focus) => { draw(); const f = focus && $(focus, node); if (f) { f.focus(); if (f.setSelectionRange) f.setSelectionRange(f.value.length, f.value.length); } };
    node.addEventListener('input', (e) => { if (e.target.id === 'rp-pq') { q = e.target.value; redraw('#rp-pq'); } });
    node.addEventListener('click', (e) => {
      const t = e.target.closest('[data-pid],[data-use],[data-near]'); if (!t) return;
      if (t.dataset.pid) { pick = t.dataset.pid; redraw('[data-pid="' + t.dataset.pid.replace(/"/g, '') + '"]'); }
      else if (t.hasAttribute('data-near')) {
        if (!navigator.geolocation) { status = { kind: '', icon: 'alert', text: 'Location is off. Search for a place by name.' }; return redraw(); }
        status = { kind: 'info', icon: 'spinner', text: 'Finding places near you' }; redraw();
        navigator.geolocation.getCurrentPosition((p) => { here = [p.coords.latitude, p.coords.longitude]; status = ''; redraw('[data-near]'); }, () => { status = { kind: '', icon: 'alert', text: 'Location is off. Search for a place by name.' }; redraw(); }, { timeout: 8000, maximumAge: 60000 });
      } else if (t.hasAttribute('data-use')) {
        if (pick === '__none') { R.noPlace = true; R.place = null; R.stars = 0; R.parts = {}; }
        else if (pick) { R.noPlace = false; R.place = placeById(pick); const ex = rated(pick); R.existing = ex && ex.overall ? ex : null; if (R.existing) { R.stars = ex.overall; R.parts = { entrance: ex.entrance, restroom: ex.restroom, parking: ex.parking, inside: ex.inside }; R.banner = { kind: 'info', icon: 'check', text: 'You rated this place ' + ex.overall + ' of 5. You can change it.' }; } }
        R.errors = R.errors.filter((x) => x[0] !== 'place');
        sheet.close(); render('#rp-place [data-change]');
      }
    });
  }
  function keepSheet() {
    const row = (ic, t) => '<li>' + icon(ic) + '<span>' + t + '</span></li>';
    ui.sheet.open({ title: 'What we keep', html: '<h3 class="sec">A rating</h3><ul class="keep">' + row('star', 'Your stars, for the whole place and any parts you tap') + row('clock', 'Visit month and who you are, if you add them') + row('settings', 'Your comment: saved for research, never published') + row('list', 'A random code for this device, to keep one rating per place') + '</ul><h3 class="sec">A problem</h3><ul class="keep">' + row('alert', 'The problem, your comment and the place') + row('image', 'Your photo, if you add one, without location data') + row('settings', 'Your device type and the page address') + row('send', 'Your email or phone, only if you add it') + '</ul><h3 class="sec">We do not keep</h3><ul class="keep">' + row('no', 'No name or account') + row('no', 'No IP address in our tables') + row('no', 'Comments and photos are never shown to the public') + '</ul><p class="muted small">Only the average of all stars is public. The team and researchers read comments and problems. Problems are deleted after 24 months, and you can delete one right after sending.</p><button type="button" class="btn btn-primary block" data-sheet-close data-autofocus>Got it</button>' });
  }
  function deleteSheet(id) {
    const m = mine().find((x) => x.k === 'problem' && x.id === id);
    let s;
    s = ui.sheet.open({ title: 'Delete this report?', html: '<p class="muted">We remove the text and photo. ' + (R.outcome && R.outcome.rating ? 'Your rating stays. ' : '') + 'This cannot be undone.</p><p class="small muted" id="rp-del-msg" role="status" aria-live="polite"></p><button type="button" class="btn btn-secondary block" data-sheet-close data-autofocus>Keep report</button><button type="button" class="btn btn-danger block" data-really>' + icon('trash') + '<span>Delete report</span></button>' });
    $('[data-really]', s.el).addEventListener('click', async (e) => {
      const b = e.currentTarget; b.disabled = true;
      try {
        const r = await rpc('delete_problem_report', { p_report_id: id, p_device_id: DEVICE });
        if (!r.ok) throw new Error('delete failed');
        await r.json();
        setMine(mine().filter((x) => !(x.k === 'problem' && x.id === id)));
        s.close();
        if (R) { R.view = R.view === 'mine' ? 'mine' : 'deleted'; render(); }
      } catch (err) { b.disabled = false; $('#rp-del-msg', s.el).textContent = 'It could not be deleted just now. Please try again.'; }
    });
    void m;
  }

  // ---- events
  document.addEventListener('click', (e) => {
    if (!root || !root.contains(e.target)) return;
    const t = e.target.closest('[data-act],[data-change],[data-part],[data-who],[data-problem],[data-cam],[data-pick],[data-rm],[data-fix],[data-del],[data-change-rating]');
    if (!t) return;
    const d = t.dataset;
    if (d.act === 'close' || d.act === 'done') { close(); return; }
    if (d.act === 'back') { if (R.view === 'form') close(); else { R.view = 'form'; render(); } return; }
    if (d.act === 'keep') { keepSheet(); return; }
    if (d.act === 'mine') { R.view = 'mine'; render(); return; }
    if (d.act === 'form') { R.view = 'form'; render(); return; }
    if (d.act === 'again') { const keep = opener; close({ noFocus: true }); open(null, keep); return; }
    if (d.act === 'again-place') { const p = R.place, keep = opener; close({ noFocus: true }); open(p ? { placeId: p.id, region: p.region } : null, keep); const pr = $('[data-problem="blocked"]', root); if (pr) pr.focus(); return; }
    if (d.act === 'change') { const p = R.place, keep = opener; close({ noFocus: true }); open(p ? { placeId: p.id, region: p.region } : null, keep); return; }
    if ('change' in d) { placeSheet(); return; }
    if ('changeRating' in d) { const keep = opener; close({ noFocus: true }); open({ placeId: d.changeRating }, keep); return; }
    if ('del' in d) { deleteSheet(d.del); return; }
    if ('part' in d) { const k = d.part, v = +d.v; R.parts[k] = R.parts[k] === v ? null : v; saveDraft(); render('[data-part="' + k + '"][data-v="' + v + '"]'); return; }
    if ('who' in d) { R.who = R.who === d.who ? '' : d.who; saveDraft(); render('[data-who="' + d.who + '"]'); return; }
    if ('problem' in d) { R.problem = R.problem === d.problem ? '' : d.problem; R.errors = R.errors.filter((x) => x[0] !== 'problem' && x[0] !== 'photo' && !(x[0] === 'stars' && R.problem)); saveDraft(); render('[data-problem="' + d.problem + '"]'); return; }
    if ('cam' in d) { $('#rp-cam', root).click(); return; }
    if ('pick' in d) { $('#rp-file', root).click(); return; }
    if ('rm' in d) { if (R.photoUrl) URL.revokeObjectURL(R.photoUrl); R.photo = R.photoUrl = null; R.photoMsg = 'Photo removed.'; R.photoErr = ''; R.errors = R.errors.filter((x) => x[0] !== 'photo'); render('[data-pick]'); return; }
    if ('fix' in d) {
      e.preventDefault();
      const map = { place: '#rp-place [data-change]', stars: 'input[name=rp-star]', problem: '[data-problem]', comment: '#rp-comment', photo: '[data-pick]' };
      if (d.fix === 'comment' || d.fix === 'photo') { R.openExtra = true; const ex = $('#rp-extra', root); if (ex) ex.open = true; }
      const el = $(map[d.fix], root); if (el) el.focus();
    }
  });
  // ui.sheet binds only the first [data-sheet-close]: make every close button in a modal sheet close it (B0 gap, see docs/ui_components.md)
  document.addEventListener('click', (e) => { const b = e.target.closest('.sheet.modal [data-sheet-close]'); if (!b) return; const first = b.closest('.sheet.modal').querySelector('[data-sheet-close]'); if (first !== b) first.click(); });
  document.addEventListener('submit', (e) => { if (root && root.contains(e.target)) { e.preventDefault(); send(); } });
  document.addEventListener('change', (e) => {
    if (!root || !root.contains(e.target)) return;
    const t = e.target;
    if (t.name === 'rp-star') { R.stars = +t.value; R.errors = R.errors.filter((x) => x[0] !== 'stars'); saveDraft(); render('input[name=rp-star]:checked'); }
    else if (t.id === 'rp-visit') { R.visit = t.value; saveDraft(); }
    else if (t.id === 'rp-cam' || t.id === 'rp-file') { takePhoto(t.files[0]); t.value = ''; }
  });
  document.addEventListener('input', (e) => {
    if (!root || !root.contains(e.target)) return;
    if (e.target.id === 'rp-comment') { R.comment = e.target.value; saveDraft(); const c = $('#rp-count', root); if (c) c.textContent = R.comment.length + ' of ' + limit(); e.target.toggleAttribute('aria-invalid', R.comment.length > limit()); if (R.comment.length > limit()) e.target.setAttribute('aria-invalid', 'true'); else e.target.removeAttribute('aria-invalid'); }
    else if (e.target.id === 'rp-contact') { R.contact = e.target.value; saveDraft(); }
  });
  document.addEventListener('toggle', (e) => { if (!root || !R) return; if (e.target.id === 'rp-more') R.openMore = e.target.open; if (e.target.id === 'rp-extra') R.openExtra = e.target.open; }, true);
  ['atlas:open-saved', 'atlas:open-ask'].forEach((n) => document.addEventListener(n, () => { if (root) close({ noFocus: true }); }));
  if (CFG) atlas.on('atlas:open-report', (d) => open(d || {}));
  window.AtlasReport = { open, close, setPlaces, state: () => R, PLACES, validate: () => R && validate() };
})();
