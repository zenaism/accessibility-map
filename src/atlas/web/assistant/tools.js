/* Openway Assistant: the lookup tools and the executor over the exported JSON (port of tools.py + executor.py).
   Same names, same results as the Python tools on the DuckDB knowledge base; golden tests check it. */
(function (g) {
  'use strict';
  const O = (g.Openway = g.Openway || {});
  const T = g.Openway.text || require('./text.js');
  const D = g.Openway.dates || require('./dates.js');
  const COMPASS = ['north', 'northeast', 'east', 'southeast', 'south', 'southwest', 'west', 'northwest'];
  const RATING_ORDER = { accessible: 0, partial: 1, not_accessible: 2, unknown: 3 };
  const FALLBACK_NEED = { step_free_entrance: 'listed_wheelchair_accessible' };
  const nz = v => (v === undefined || v === '' ? null : v);

  /** KB from the region files: rows shaped like the DuckDB `places` rows. */
  function buildKB(regionFiles) {
    const kb = { places: [], byId: new Map(), facts: new Map(), events: [], areas: {}, generated: null, site: null };
    for (const f of regionFiles) {
      kb.generated = kb.generated && kb.generated > f.generated ? kb.generated : f.generated;
      kb.site = f.site;
      const start = kb.places.length;
      for (const p of f.places) {
        const row = {
          link_id: p.id, name: p.name, region: f.region, layer: p.layer, rating: p.rating,
          lat: nz(p.lat), lon: nz(p.lon), summary: p.summary || '', notice: nz(p.notice),
          keys: p.keys || [], newest_source: nz(p.newest_source), address: nz(p.address), phone: nz(p.phone),
          website: nz(p.website), hours: nz(p.hours), arrival: nz(p.arrival), route: p.route || null,
          page: p.page || (f.site + '/places/' + f.region + '/' + p.id + '.html'),
        };
        kb.places.push(row); kb.byId.set(row.link_id, row); kb.facts.set(row.link_id, []);
      }
      for (const x of f.facts) {
        const id = f.places[x[0]].id;
        kb.facts.get(id).push({ attribute: x[1], value: x[2], detail: x[3], quote: x[4], source: x[5], date: x[6] });
      }
      for (const e of f.events) {
        const row = kb.places[start + e[0]];
        kb.events.push({ link_id: row.link_id, title: e[1], start: e[2], url: e[3], access: e[4], accessible_tag: !!e[5], disability_focused: !!e[6], place: row.name, rating: row.rating, page: row.page, region: row.region });
      }
      Object.assign(kb.areas, f.areas || {});
    }
    kb.names = kb.places.map(p => p.name.toLowerCase());
    return kb;
  }

  const miles = (lat1, lon1, lat2, lon2) => {
    const r = 3958.8, rad = Math.PI / 180, p1 = lat1 * rad, p2 = lat2 * rad;
    const a = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin((lon2 - lon1) * rad / 2) ** 2;
    return 2 * r * Math.asin(Math.sqrt(a));
  };
  function direction(lat1, lon1, lat2, lon2) {
    const rad = Math.PI / 180;
    const y = Math.sin((lon2 - lon1) * rad) * Math.cos(lat2 * rad);
    const x = Math.cos(lat1 * rad) * Math.sin(lat2 * rad) - Math.sin(lat1 * rad) * Math.cos(lat2 * rad) * Math.cos((lon2 - lon1) * rad);
    const deg = Math.atan2(y, x) / rad;
    return COMPASS[T.rhu((((deg + 360) % 360)) / 45) % 8];
  }
  const round2 = x => Math.round(x * 100) / 100;

  function words(s) {
    const stop = new Set(['the', 'a', 'an', 'of', 'in', 'at', 'and', 'is', 'to', 'for', 'on', 'my', 'me', 'near']);
    return (String(s || '').toLowerCase().match(/[a-z0-9']+/g) || []).filter(w => !stop.has(w) && w.length > 1);
  }

  function Backend(kb, rules) {
    const NEEDS = rules.NEEDS, POSITIVE = new Set(rules.POSITIVE);
    const idsWithNeed = need => {
      const spec = NEEDS[need], ids = new Set();
      if (spec.facts) {
        const attrs = new Set(spec.facts);
        for (const [id, fs] of kb.facts) for (const f of fs) {
          if (attrs.has(f.attribute) && POSITIVE.has(String(f.value).split(';').pop())) { ids.add(id); break; }
        }
      }
      if (spec.restroom_layer) for (const p of kb.places) if (p.layer === 'restroom' && (p.rating === 'accessible' || p.rating === 'partial')) ids.add(p.link_id);
      if (spec.layers) for (const p of kb.places) if (spec.layers.includes(p.layer)) ids.add(p.link_id);
      return ids;
    };
    const brief = (row, here) => {
      const out = {
        link_id: row.link_id, name: row.name, region: row.region, type: row.layer, rating: row.rating,
        what_is_known: row.keys, summary: row.summary, notice: row.notice, newest_source: row.newest_source,
        page: row.page, address: row.address, phone: row.phone, website: row.website, hours: row.hours,
      };
      if (here) { out.miles = round2(miles(here[0], here[1], row.lat, row.lon)); out.direction = direction(here[0], here[1], row.lat, row.lon); }
      return out;
    };
    const factText = {};
    let weightCache = {};
    const be = {
      places() { return kb.places.map(p => ({ id: p.link_id, name: p.name, layer: p.layer, region: p.region, rating: p.rating, lat: p.lat, lon: p.lon })); },
      as_of() { return kb.generated; },
      coords(id) { const p = kb.byId.get(id); return p ? [p.lat, p.lon] : [null, null]; },
      facts(id) { return (kb.facts.get(id) || []).map(f => Object.assign({}, f)); },
      search_places(a) {
        const region = a.region || null, type = a.place_type || null, need = a.need || null, limit = a.limit || 5;
        let rows = kb.places.filter(r => (!region || r.region === region) && (!type || r.layer === type));
        if (need) { const ok = idsWithNeed(need); rows = rows.filter(r => ok.has(r.link_id)); }
        const ws = words(a.query || '');
        const text = {};
        if (ws.length) {
          for (const [id, fs] of kb.facts) if (fs.length) text[id] = fs.map(f => (f.attribute + ' ' + f.detail).toLowerCase()).join(' ');
        }
        const weight = {};
        for (const w of ws) weight[w] = 1 / Math.log(2 + kb.names.reduce((n, nm) => n + (nm.includes(w) ? 1 : 0), 0));
        const scored = [];
        for (const r of rows) {
          const name = r.name.toLowerCase();
          let score = 0;
          if (ws.length) {
            let inName = 0, inBody = 0;
            for (const w of ws) if (name.includes(w)) inName += weight[w];
            const body = r.summary.toLowerCase() + ' ' + (r.address || '').toLowerCase() + ' ' + (text[r.link_id] || '');
            for (const w of ws) if (body.includes(w)) inBody += weight[w];
            if (inName === 0 && !ws.every(w => body.includes(w))) continue;
            const exact = name.includes(ws.join(' ')) ? 3 : 0;
            score = exact + 2 * inName + 0.5 * inBody;
          }
          scored.push([-score, RATING_ORDER[r.rating], -r.keys.length, r.name, r]);
        }
        scored.sort((x, y) => T.cmpKeys(x.slice(0, 4), y.slice(0, 4)));
        return scored.slice(0, limit).map(t => brief(t[4]));
      },
      nearest(a) {
        const need = a.need || null, type = a.place_type || null, maxMiles = a.max_miles == null ? 5.0 : a.max_miles, limit = a.limit || 5;
        let rows = kb.places.filter(r => r.lat !== null && (!type || r.layer === type));
        if (need) { const ok = idsWithNeed(need); rows = rows.filter(r => ok.has(r.link_id)); }
        const hits = rows.map(r => [miles(a.lat, a.lon, r.lat, r.lon), r]).sort((x, y) => x[0] - y[0]);
        return hits.filter(h => h[0] <= maxMiles).slice(0, limit).map(h => brief(h[1], [a.lat, a.lon]));
      },
      find_events(a) {
        const start = a.start, end = a.end || D.plusDays(start, 30), limit = a.limit || 10;
        let rows = kb.events.filter(e => e.start.slice(0, 10) >= start && e.start.slice(0, 10) <= end);
        if (a.region) rows = rows.filter(e => e.region === a.region);
        if (a.link_id) rows = rows.filter(e => e.link_id === a.link_id);
        if (a.disability_focused) rows = rows.filter(e => e.disability_focused);
        if (a.access && a.access.length) rows = rows.filter(e => a.access.some(x => e.access.includes(x)));
        for (const w of words(a.query || '')) rows = rows.filter(e => e.title.toLowerCase().includes(w));
        rows = rows.slice().sort((x, y) => T.cmp(x.start, y.start) || T.cmp(x.title, y.title)).slice(0, limit);
        return rows.map(e => ({ title: e.title, start: e.start, url: e.url, access: e.access.split(',').filter(Boolean), accessible_tag: e.accessible_tag, disability_focused: e.disability_focused, place: e.place, link_id: e.link_id, rating: e.rating, page: e.page }));
      },
      get_place(id) {
        const r = kb.byId.get(id);
        if (!r) {
          const hit = be.search_places({ query: id, limit: 1 });
          if (!hit.length) return null;
          return be.get_place(hit[0].link_id);
        }
        const out = brief(r);
        out.facts = be.facts(r.link_id);
        out.getting_there = r.arrival || r.route ? { arrival: r.arrival, route: r.route } : {};
        out.contacts = {};
        out.events = [];
        out.data_as_of = kb.generated;
        return out;
      },
      area_conditions(lat, lon) {
        const c = kb.areas[lat.toFixed(4) + ',' + lon.toFixed(4)];
        return c ? JSON.parse(JSON.stringify(c)) : null;
      },
      accessible_route(a) {
        const p = be.get_place(a.to);
        if (!p) return null;
        const r = (p.getting_there || {}).route;
        if (!r) return null;
        if (a.profile === 'blind' && r.blind) return Object.assign({ place: p.name, from: r.from, to: r.to }, r.blind);
        const o = { place: p.name };
        for (const k of Object.keys(r)) if (k !== 'blind') o[k] = r[k];
        return o;
      },
    };
    return be;
  }

  const enrich = (rows, be) => { for (const r of rows) { r.facts = be.facts(r.link_id); const c = be.coords(r.link_id); r.lat = c[0]; r.lon = c[1]; } return rows; };
  const upcoming = (be, args, today) => be.find_events(Object.assign({}, args, { limit: args.limit || 10 })).filter(e => e.start.slice(0, 10) >= today);

  function execute(pl, ctx, be) {
    const out = [];
    const a = Object.assign({}, pl.args);
    const R = (tool, args, data, meta) => ({ tool, args, data, meta: meta || {} });
    if (pl.tool === 'search_places' || pl.tool === 'nearest') {
      const fn = pl.tool === 'search_places' ? be.search_places : be.nearest;
      let rows = fn(a), meta = {};
      if (!rows.length && FALLBACK_NEED[a.need]) {
        const a2 = Object.assign({}, a, { need: FALLBACK_NEED[a.need] });
        rows = fn(a2);
        if (rows.length) meta = { fallback_need: a2.need, wanted: a.need };
      }
      out.push(R(pl.tool, a, enrich(rows, be), meta));
    } else if (pl.tool === 'get_place') {
      const p = be.get_place(a.name_or_id);
      if (p) { p.events = upcoming(be, { link_id: p.link_id, start: ctx.today, end: D.plusDays(ctx.today, 365) }, ctx.today); const c = be.coords(p.link_id); p.lat = c[0]; p.lon = c[1]; }
      out.push(R('get_place', a, p));
    } else if (pl.tool === 'find_events') {
      const rows = upcoming(be, a, ctx.today);
      out.push(R('find_events', a, rows, { as_of: be.as_of() }));
      if (!rows.length) {
        const nxt = {};
        for (const k of Object.keys(a)) if (k !== 'start' && k !== 'end') nxt[k] = a[k];
        nxt.start = D.plusDays(a.end, 1); nxt.end = D.plusDays(a.end, 365); nxt.limit = 3;
        out.push(R('find_events', nxt, upcoming(be, nxt, ctx.today), { role: 'next_events', as_of: be.as_of() }));
      }
    } else if (pl.tool === 'area_conditions') {
      out.push(R('area_conditions', a, be.area_conditions(a.lat, a.lon, a.region)));
      if (pl.anchor && pl.anchor.id) out.push(R('get_place', { name_or_id: pl.anchor.id }, be.get_place(pl.anchor.id)));
    } else if (pl.tool === 'accessible_route') {
      out.push(R('accessible_route', a, be.accessible_route(a)));
      out.push(R('get_place', { name_or_id: a.to }, be.get_place(a.to)));
    }
    return out;
  }
  const X = { buildKB, Backend, execute };
  O.tools = X;
  if (typeof module !== 'undefined') module.exports = X;
})(typeof globalThis !== 'undefined' ? globalThis : this);
