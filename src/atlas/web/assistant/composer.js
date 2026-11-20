/* Openway Assistant: template composer (port of composer.py). Tool results -> answer, from fixed sentence templates. */
(function (g) {
  'use strict';
  const O = (g.Openway = g.Openway || {});
  const X = g.Openway.text || require('./text.js');
  const D = g.Openway.dates || require('./dates.js');
  const R = () => O.rules;
  const { rhu } = X;
  const MAX_CARDS = 3;
  const STANDING = 'Computed from map data, not checked on site.';

  const S = (text, refs, kind, derived) => ({ text, refs: refs || [], kind: kind || 'claim', derived: derived || [] });
  const titleCase = s => s.replace(/\w\S*/g, w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());
  const trimEnd = (s, chars) => { let i = s.length; while (i > 0 && chars.includes(s[i - 1])) i--; return s.slice(0, i); };

  function clip(s, n) {
    n = n || 90;
    s = String(s).split(/\s+/).filter(Boolean).join(' ');
    if (s.length <= n) return s;
    const cut = s.slice(0, n), i = cut.lastIndexOf(' ');
    return trimEnd(i > Math.floor(n / 2) ? cut.slice(0, i) : cut, ' ,;:.') + '…';
  }
  function fullDate(iso) {
    if (!iso || iso.length < 10) return iso || '';
    return parseInt(iso.slice(8, 10), 10) + ' ' + D.cap(D.MONTHS[parseInt(iso.slice(5, 7), 10) - 1]) + ' ' + iso.slice(0, 4);
  }
  function monthYear(d) {
    if (d.length >= 10) return parseInt(d.slice(8, 10), 10) + ' ' + D.cap(D.MONTHS[parseInt(d.slice(5, 7), 10) - 1].slice(0, 3)) + ' ' + d.slice(0, 4);
    if (d.length >= 7) return D.cap(D.MONTHS[parseInt(d.slice(5, 7), 10) - 1].slice(0, 3)) + ' ' + d.slice(0, 4);
    return d;
  }
  function sourceWords(url) {
    const u = String(url || '').toLowerCase();
    for (const [host, words] of R().SOURCE_KINDS) if (u.includes(host)) return words;
    const m = u.match(/^https?:\/\/(?:www\.)?([^/]+)/);
    return m ? 'the website ' + m[1] : 'a listed source';
  }
  function ageWords(d, today) {
    if (!d) return 'no date given';
    let out = monthYear(d);
    if (/^\d{4}/.test(d) && parseInt(today.slice(0, 4), 10) - parseInt(d.slice(0, 4), 10) >= 2) out += ' (old: from ' + d.slice(0, 4) + ')';
    return out;
  }
  function distanceText(m) {
    if (m === null || m === undefined) return null;
    if (m < 0.19) return 'about ' + Math.max(50, rhu(m * 5280 / 50) * 50) + ' feet';
    return 'about ' + (rhu(m * 10) / 10).toFixed(1) + ' miles';
  }
  function fmtPhone(p) {
    if (!p) return p;
    let d = String(p).replace(/\D/g, '');
    if (d.length === 11 && d[0] === '1') d = d.slice(1);
    return d.length === 10 ? '(' + d.slice(0, 3) + ') ' + d.slice(3, 6) + '-' + d.slice(6) : p;
  }
  const joinOr = items => items.length === 1 ? items[0] : items.slice(0, -1).join(', ') + ' or ' + items[items.length - 1];
  const needLabel = need => R().NEED_LABELS[need || ''] || '';
  const factLabel = a => R().FACT_LABELS[a] || a;
  function factText(f) {
    const label = factLabel(f.attribute), v = String(f.value), d = clip(f.detail || '');
    return label + ': ' + v + (d ? ' (' + d + ')' : '');
  }
  const positive = f => new Set(R().POSITIVE).has(String(f.value).split(';').pop().trim());
  function pickFacts(facts, need, k) {
    k = k === undefined ? 4 : k;
    const attrs = new Set(((R().NEEDS[need || ''] || {}).facts) || []);
    let rel = facts.filter(f => attrs.has(f.attribute) && positive(f));
    rel = rel.filter(f => f.quote).concat(rel.filter(f => !f.quote));
    if (!rel.length) {
      let rest = facts.filter(f => !R().NOISE_FACTS.includes(f.attribute));
      rest = rest.filter(f => f.quote).concat(rest.filter(f => !f.quote));
      const pr = a => { const i = R().FACT_PRIORITY.indexOf(a); return i >= 0 ? i : 99; };
      rest = rest.map((f, i) => [f, i]).sort((x, y) => (pr(x[0].attribute) - pr(y[0].attribute)) || (x[1] - y[1])).map(x => x[0]);
      rel = rest.length ? rest : facts;
    }
    return rel.slice(0, k);
  }
  const toFact = (f, pid) => ({ label: factLabel(f.attribute), value: String(f.value), detail: f.detail || '', quote: f.quote || '', source: f.source || '', date: f.date || '', place_id: pid });
  function cardFor(row, need, ctx, k) {
    const facts = pickFacts(row.facts || [], need, k === undefined ? 4 : k);
    const seen = new Set(), sources = [];
    for (const f of facts) {
      const key = f.source || '';
      if (key && !seen.has(key)) { seen.add(key); sources.push({ url: key, date: f.date || '', quote: f.quote || '', label: sourceWords(key) }); }
    }
    const m = row.miles === undefined ? null : row.miles;
    return {
      place_id: row.link_id, name: row.name, type: R().TYPE_LABELS[row.type] || row.type || '', rating: row.rating,
      facts: facts.map(f => toFact(f, row.link_id)), sources, miles: m, direction: row.direction === undefined ? null : row.direction,
      distance_text: distanceText(m), phone: fmtPhone(row.phone) || null, note: row.notice || null,
      lat: row.lat === undefined ? null : row.lat, lon: row.lon === undefined ? null : row.lon, event: null,
    };
  }
  function eventCard(e) {
    return {
      place_id: e.link_id, name: e.place, type: 'event', rating: e.rating, facts: [],
      sources: e.url ? [{ url: e.url, date: '', quote: '', label: sourceWords(e.url) }] : [],
      miles: null, direction: null, distance_text: null, phone: null, note: null, lat: null, lon: null,
      event: { title: e.title, start: e.start, when_text: D.whenText(e.start), url: e.url || '', access: (e.access || []).map(a => R().ACCESS_WORDS[a] || a) },
    };
  }
  function sourcesOf(cards) {
    const out = [], seen = new Set();
    for (const c of cards) for (const s of c.sources) if (!seen.has(s.url)) { seen.add(s.url); out.push(s); }
    return out;
  }
  const dataOf = (results, tool, role) => results.find(r => r.tool === tool && ((r.meta || {}).role || null) === (role || null)) || null;
  const callOf = row => (row && row.phone ? { name: row.name, phone: fmtPhone(row.phone) } : null);
  function A(kind, headline, f) {
    return Object.assign({
      kind, headline: headline.slice(0, 2), details: [], cards: [], unknown: [], call: null, actions: [], sources: [],
      clarify: null, as_of: null, notes: [], verified: false, removed: 0, plan: null, engine: 'rules',
    }, f || {});
  }

  function compose(pl, results, ctx, asOf) {
    const fn = {
      emergency, help, ada_trust: trust, conflict_trust: trust, reports_trust: trust, dates_trust: trust,
      out_of_area: outOfArea, no_data: noData, live_info: live, events, route, area, nearest: list, search: list, place, clarify, unknown,
    }[pl.intent];
    const a = fn(pl, results, ctx, asOf);
    a.plan = pl;
    a.as_of = ['emergency', 'out_of_area', 'help', 'clarify'].includes(pl.intent) ? null : (asOf === undefined ? null : asOf);
    return a;
  }
  const emergency = () => A('emergency', [S('If this is an emergency, call 911 now.', [], 'meta')], { actions: [{ type: 'call', name: 'Emergency services', phone: '911' }] });
  const help = () => A('help', [S('I can look things up about accessible places in Cincinnati and Oxford.', [], 'meta'), S("Each answer shows its source. I say so when I don't know.", [], 'meta')],
    { details: [S('I can answer: ' + R().CAN_ANSWER.join('; ') + '.', [], 'meta'), S('I cannot answer: ' + R().CANNOT_ANSWER.join('; ') + '.', [], 'meta')] });
  const outOfArea = pl => A('out_of_area', [S('I only cover Cincinnati and Oxford for now.', [], 'meta'), S("I can't help with " + pl.topic + ' yet.', [], 'meta')], { unknown: [pl.topic] });
  const noData = pl => A('no_data', [S("I don't have information about " + pl.topic.toLowerCase() + ' yet.', [], 'meta'), S('I can look up restrooms, parking, places to eat, events and trails.', [], 'meta')],
    { details: [S('I can answer: ' + R().CAN_ANSWER.join('; ') + '.', [], 'meta')], unknown: [pl.topic] });
  const unknown = () => A('unknown', [S("I didn't understand that, or I don't have the data to answer it.", [], 'meta'),
    S('Try a button below, or ask about a restroom, parking, food, events, a trail or a place by name.', [], 'meta')], { unknown: ['that question'] });
  const clarify = pl => A('clarify', [S(pl.clarify.question, [], 'meta')], { clarify: pl.clarify });

  function live(pl, res, ctx, asOf) {
    const place = dataOf(res, 'get_place'), row = place && place.data ? place.data : null;
    const first = S("I can't tell you " + pl.topic + ' because my information is a saved snapshot, not live.', [], 'meta');
    const second = S('It was last updated ' + fullDate(asOf) + '.', [], 'meta');
    const det = []; let call = null;
    if (row) {
      call = callOf(row);
      if (row.hours) det.push(S('The listing for ' + row.name + ' says hours are: ' + row.hours + '. This may be out of date.', [row.link_id]));
      if (call) det.push(S('To be sure, call ' + row.name + ' at ' + call.phone + '.', [row.link_id]));
      else det.push(S('Check with ' + row.name + ' directly.', [row.link_id]));
    } else det.push(S('Check with the venue or agency directly for live information.', [], 'meta'));
    const cards = row ? [cardFor(row, null, ctx)] : [];
    return A('unknown', [first, second], { details: det, cards, call, unknown: [pl.topic], sources: sourcesOf(cards) });
  }

  function trust(pl, res, ctx, asOf) {
    const place = dataOf(res, 'get_place'), row = place && place.data ? place.data : null;
    const name = row ? row.name : null;
    const cards = row ? [cardFor(row, null, ctx, 5)] : [];
    const refs = row ? [row.link_id] : [];
    const det = []; let head;
    if (pl.intent === 'ada_trust') {
      head = [S("I can't say whether a place is ADA compliant or safe. That takes a formal survey.", [], 'disclaimer'),
        S(name ? 'Here is what public sources say about ' + name + '.' : 'I only collect what public sources say, with dates.', refs, 'meta')];
      if (row) det.push(S('Map rating for ' + name + ': ' + R().RATING_TEXT[row.rating].toLowerCase() + ', from the facts on the card.', refs));
    } else if (pl.intent === 'conflict_trust') {
      head = [S('Sources can disagree, so I show each source and its date.', [], 'meta'),
        S(name ? 'For ' + name + ', check the card to see which source says what.' : 'Tell me which place you mean.', refs, 'meta')];
      if (row) {
        const n = new Set(row.facts.filter(f => f.source).map(f => f.source)).size;
        det.push(S('I have ' + n + ' sources for ' + name + '. If they disagree, trust the newest and call to check.', refs, 'claim', [String(n)]));
      }
    } else if (pl.intent === 'reports_trust') {
      head = [S("I can't confirm what people say on social media. I only use sources I can name and date.", [], 'meta'),
        S(name ? 'If you saw a problem at ' + name + ', use Report a problem so it can be checked.' : 'If you saw a problem, use Report a problem so it can be checked.', refs, 'meta')];
    } else {
      head = [S('My information is a snapshot from ' + fullDate(asOf) + '. Each fact shows the date of its source.', [], 'meta')];
      if (row) { const nv = row.newest_source; head.push(S(nv ? 'For ' + name + ', the newest source is dated ' + monthYear(nv) + '.' : 'For ' + name + ', I have no dated source.', refs)); }
      det.push(S('Events are refreshed more often than places. Always call ahead for anything important.', [], 'meta'));
    }
    const actions = [{ type: 'report', text: name ? 'Problem with information about ' + name + ': ' : 'Problem with information: ' }];
    return A('answer', head, { details: det, cards, actions, call: callOf(row), sources: sourcesOf(cards) });
  }

  function evidence(row, need, ctx) {
    const facts = pickFacts(row.facts || [], need, 1);
    if (!facts.length) return [null, null];
    const f = facts[0];
    return [S(factText(f) + '. Source: ' + sourceWords(f.source) + ', ' + ageWords(f.date || '', ctx.today) + '.', [row.link_id]), f];
  }

  function list(pl, res, ctx) {
    const r = res.length ? res[0] : null;
    const rows = (r && r.data) || [];
    const plain = ctx.plain;
    const fb = r && r.meta && r.meta.fallback_need;
    const need = fb ? fb : pl.need;
    const where = pl.anchor && pl.anchor.name !== 'your location' ? 'near ' + pl.anchor.name : (pl.anchor ? 'near you' : '');
    const ask = needLabel(pl.need) || R().TYPE_LABELS[pl.place_type || ''] || '';
    if (!rows.length) {
      let msg;
      if (pl.args.query) msg = "I don't have anything about " + pl.args.query + (pl.need && ask ? ' with ' + ask : '') + ' in my data.';
      else if (pl.need && ask) msg = "I don't have a place with " + ask + (where ? ' ' + where : '') + ' in my data.';
      else msg = "I don't have a matching place" + (where ? ' ' + where : '') + ' in my data.';
      return A('unknown', [S(msg, [], 'meta'), S("I don't know, and I would rather say so than guess.", [], 'meta')],
        { unknown: [ask || 'that'].concat(pl.unsupported), details: [S('Try another area or another need, or call the place to ask.', [], 'meta')] });
    }
    const cards = rows.slice(0, MAX_CARDS).map(x => cardFor(x, need, ctx));
    const first = rows[0], nm = first.name, refs = [first.link_id];
    let lead;
    if (pl.intent === 'nearest' && first.miles !== undefined && first.miles !== null) {
      const anchorT = pl.anchor.name === 'your location' ? 'you' : pl.anchor.name;
      const of = cards[0].distance_text + ' ' + first.direction + ' of ' + anchorT;
      lead = pl.need ? 'The closest place I found with ' + ask + ' is ' + nm + ', ' + of + '.' : 'The closest ' + (ask || 'place') + ' I found is ' + nm + ', ' + of + '.';
      if (pl.anchor.name === nm) lead = pl.need ? nm + ' itself has ' + ask + ' on record.' : nm + ' itself is the closest.';
      if (plain) lead = pl.need ? 'Closest with ' + ask + ': ' + nm + ', ' + of + '.' : 'Closest: ' + nm + ', ' + of + '.';
    } else if (pl.need) {
      lead = rows.length > 1 ? rows.length + ' places have ' + ask + ' on record. The first is ' + nm + '.' : 'One place has ' + ask + ' on record: ' + nm + '.';
    } else {
      lead = rows.length > 1 ? 'I found ' + rows.length + ' places that match. The first is ' + nm + '.' : 'I found one place that matches: ' + nm + '.';
    }
    const derived = [String(rows.length)];
    if (cards[0].distance_text) derived.push(cards[0].distance_text.replace(/[^0-9.]/g, ''));
    const sents = [S(lead, refs, 'claim', derived)];
    const [ev] = evidence(first, need, ctx);
    if (fb) {
      sents.push(S(plain ? 'No step-free entrance is on record here. These are listed as wheelchair accessible, not checked on site.'
        : 'None of them has a step-free entrance on record, so these are listed as wheelchair accessible by volunteers on OpenStreetMap, not checked on site.', refs));
    } else if (ev) sents.push(ev);
    else sents.push(S('I have no detailed facts for it. Call before you go.', refs));
    const det = [];
    if (rows.length > 1) {
      const names = rows.slice(1, 6).map(x => { const d = distanceText(x.miles); return d ? x.name + ' (' + d + ' ' + x.direction + ')' : x.name; });
      det.push(S('Also on record: ' + names.join('; ') + '.', rows.slice(1, 6).map(x => x.link_id)));
    }
    if (fb && ev) det.push(ev);
    if (r.meta && r.meta.private_removed) { const n = r.meta.private_removed; det.push(S('I left out ' + n + ' restroom' + (n > 1 ? 's' : '') + ' that OpenStreetMap marks as private.', ['tool:' + r.tool], 'claim', [String(n)])); }
    if (pl.intent === 'nearest') det.push(S('Distances are in a straight line, not a route. Not checked on site.', [], 'meta'));
    if (first.notice) det.push(S('Note for ' + nm + ': ' + first.notice + '.', refs));
    const ids = rows.filter(x => x.lat !== undefined && x.lat !== null).map(x => x.link_id);
    return A('answer', sents, { details: det, cards, unknown: pl.unsupported.slice(), call: callOf(first), actions: ids.length ? [{ type: 'show_on_map', ids }] : [], sources: sourcesOf(cards) });
  }

  function ratingLine(row) {
    const base = (R().RATING_TEXT[row.rating] || 'No accessibility rating yet') + ' on the map.';
    return base + (row.newest_source ? ' Newest source: ' + monthYear(row.newest_source) + '.' : '');
  }
  function focusSentence(row, need) {
    const label = needLabel(need);
    const attrs = new Set(((R().NEEDS[need] || {}).facts) || []);
    const facts = (row.facts || []).filter(f => attrs.has(f.attribute));
    const pos = facts.filter(positive);
    if (pos.length) return [S('Yes, ' + row.name + ' lists ' + label + '.', [row.link_id]), pos[0]];
    if (facts.length) return [S(row.name + ' lists ' + label + ' as: ' + factText(facts[0]) + '.', [row.link_id]), facts[0]];
    return [S("I don't have information about " + label + ' at ' + row.name + '.', [row.link_id], 'claim'), null];
  }

  function place(pl, res, ctx) {
    const r = dataOf(res, 'get_place'), row = r ? r.data : null;
    if (!row) return A('unknown', [S("I don't have that place in my data.", [], 'meta'), S("I don't know, and I would rather say so than guess.", [], 'meta')], { unknown: ['that place'] });
    const refs = [row.link_id], nm = row.name;
    const unk = [];
    if (!row.hours) unk.push('opening hours');
    if (!row.phone) unk.push('phone number');
    for (const w of pl.unsupported) unk.push(w);
    if (pl.unmatched.length) {
      const mism = pl.unmatched.map(titleCase).join(' ');
      const cards = [cardFor(row, null, ctx, 4)];
      return A('unknown', [S("I don't have " + nm + ' on ' + mism + ' in my data.', [], 'meta'),
        S('The only ' + nm + ' I know is in ' + titleCase(row.region) + ', so it may not be the one you mean.', refs)],
      { cards, unknown: [nm + ' on ' + mism], call: callOf(row), sources: sourcesOf(cards) });
    }
    let head, cards;
    if (pl.need && pl.need !== 'listed_wheelchair_accessible') {
      const [s1, f] = focusSentence(row, pl.need);
      let s2;
      if (f) s2 = S(factText(f) + '. Source: ' + sourceWords(f.source) + ', ' + ageWords(f.date || '', ctx.today) + '.', refs);
      else { s2 = S('Here is what I do know about ' + nm + ': ' + ratingLine(row), refs); unk.unshift(needLabel(pl.need)); }
      head = [s1, s2]; cards = [cardFor(row, pl.need, ctx, 5)];
    } else {
      const facts = pickFacts(row.facts || [], null, 1);
      const s1 = S(nm + ': ' + ratingLine(row), refs);
      const s2 = facts.length ? S(factText(facts[0]) + '. Source: ' + sourceWords(facts[0].source) + ', ' + ageWords(facts[0].date || '', ctx.today) + '.', refs)
        : S('I have no detailed facts for it yet. Call before you go.', refs);
      head = [s1, s2]; cards = [cardFor(row, null, ctx, 5)];
    }
    const det = [];
    if (row.summary) det.push(S('About: ' + clip(row.summary, 300), refs));
    if (row.hours) det.push(S('Hours listed: ' + row.hours + '.', refs));
    if (row.address) det.push(S('Address: ' + row.address + '.', refs));
    if (row.notice) det.push(S('Note: ' + row.notice + '.', refs));
    const gt = row.getting_there || {};
    if (gt.arrival) det.push(S('Getting there: ' + gt.arrival + ' Computed from map data, not checked on site.', refs));
    const ev = row.events || [];
    if (ev.length) det.push(S('Next event I have: ' + ev[0].title + ', ' + D.whenText(ev[0].start) + '.', refs));
    const hasPt = row.lat !== undefined && row.lat !== null;
    return A('answer', head, { details: det, cards, unknown: unk, call: callOf(row), actions: hasPt ? [{ type: 'show_on_map', ids: refs }] : [], sources: sourcesOf(cards) });
  }

  function events(pl, res, ctx, asOf) {
    const r = dataOf(res, 'find_events'), nxt = dataOf(res, 'find_events', 'next_events');
    const rows = (r && r.data) || [];
    const w = pl.when || null;
    const span = w ? D.rangeText(w) : 'in the next 30 days';
    const label = w ? w.label : 'in the next 30 days';
    const snap = S(ctx.plain ? 'Events data is from ' + fullDate(asOf) + '. It is a snapshot. Check with the venue.'
      : 'Events data was last updated ' + fullDate(asOf) + '. It is a snapshot, so check with the venue.', ['tool:find_events'], 'claim');
    const adj = pl.access.length ? joinOr(pl.access.map(a => R().ACCESS_ADJ[a] || a)) + ' ' : '';
    const spantxt = w && w.start !== w.end ? ' (' + span + ')' : '';
    if (!rows.length) {
      const nrows = (nxt && nxt.data) || [];
      const head = [S('I found no ' + adj + 'events ' + label + spantxt + '.', ['tool:find_events'], 'claim')];
      if (nrows.length) {
        const e = nrows[0];
        head.push(S('The next one I have is ' + e.title + ', ' + D.whenText(e.start) + ', at ' + e.place + '.', [e.link_id]));
        const cards = nrows.slice(0, MAX_CARDS).map(eventCard);
        return A('unknown', head, { details: [snap], cards, unknown: ['events in that time'], sources: sourcesOf(cards) });
      }
      head.push(snap);
      return A('unknown', head, { unknown: ['events in that time'] });
    }
    const e = rows[0];
    const s1 = rows.length > 1 ? 'I found ' + rows.length + ' ' + adj + 'events ' + label + '. The first is ' + e.title + ', ' + D.whenText(e.start) + ', at ' + e.place + '.'
      : 'I found one ' + adj + 'event ' + label + ': ' + e.title + ', ' + D.whenText(e.start) + ', at ' + e.place + '.';
    const head = [S(s1, [e.link_id], 'claim', [String(rows.length)]), snap];
    const cards = rows.slice(0, MAX_CARDS).map(eventCard);
    const det = [];
    for (const x of rows.slice(1, 8)) {
      const acc = (x.access || []).map(a => R().ACCESS_WORDS[a] || a).join(', ');
      det.push(S(x.title + ', ' + D.whenText(x.start) + ', at ' + x.place + (acc ? ' (' + acc + ').' : '.'), [x.link_id]));
    }
    if (e.access && e.access.length) det.unshift(S('Access for the first event: ' + e.access.map(a => R().ACCESS_WORDS[a] || a).join(', ') + '.', [e.link_id]));
    const ids = X.unique(rows.map(x => x.link_id));
    return A('answer', head, { details: det, cards, unknown: pl.unsupported.slice(), actions: [{ type: 'show_on_map', ids }], sources: sourcesOf(cards) });
  }

  function route(pl, res, ctx) {
    const r = dataOf(res, 'accessible_route'), p = dataOf(res, 'get_place');
    const row = p && p.data ? p.data : null, d = r ? r.data : null;
    const nm = row ? row.name : pl.place.name;
    if (!d) return A('unknown', [S("I don't have a step-free route to " + nm + ' yet.', [], 'meta'), S("I don't know, and I would rather say so than guess.", [], 'meta')], { unknown: ['a route'], call: callOf(row) });
    const refs = [pl.place.id];
    const s1 = S('A step-free route to ' + nm + ' from ' + d.from + ' is about ' + d.length_feet + ' feet.', refs, 'claim', [String(d.length_feet)]);
    const s2 = S('It avoids mapped stairs and steep sections. It is computed from map data, not checked on site.', [], 'meta');
    const det = (d.directions || []).map(x => S(x, refs, 'claim'));
    if (d.crossings_text) det.push(S(d.crossings_text, refs));
    if (d.compared_with_shortest) det.push(S(d.compared_with_shortest, refs));
    const cards = row ? [cardFor(row, null, ctx, 3)] : [];
    return A('answer', [s1, s2], { details: det, cards, call: callOf(row), actions: [{ type: 'route_to', place_id: pl.place.id, profile: pl.args.profile || 'wheelchair' }], sources: sourcesOf(cards) });
  }

  function area(pl, res, ctx) {
    const r = dataOf(res, 'area_conditions'), d = r ? r.data : null;
    const nm = pl.anchor ? pl.anchor.name : 'that area';
    if (!d || !d.path_sections) return A('unknown', [S("I don't have path data around " + nm + '.', [], 'meta'), S("I don't know, and I would rather say so than guess.", [], 'meta')], { unknown: ['paths and slopes'] });
    const T = ['tool:area_conditions'];
    const pct = d.share_steeper_than_ramp !== null && d.share_steeper_than_ramp !== undefined ? rhu(d.share_steeper_than_ramp * 100) : null;
    const rep = d.open_311_reports === undefined ? null : d.open_311_reports;
    const slope = S('Around ' + nm + ', about ' + pct + '% of mapped path sections are steeper than a ramp (8.33%). There are ' + d.stairways + ' mapped stairways.', T, 'claim', [String(pct), String(d.stairways)]);
    const unk = [], det = []; let head;
    if (pl.topic === 'reports' && rep === null) {
      head = [S("I don't have closure or construction information for " + nm + '.', [], 'meta'), slope];
      unk.push('closures and construction');
    } else if (pl.topic === 'reports') {
      head = [S('Near ' + nm + ', ' + rep.length + ' sidewalk or curb problems are open with the city (311). Data through ' + fullDate(d['311_data_through']) + '.', T, 'claim', [String(rep.length)]),
        S('Reports are not closures, and they are not limited to this week. Check with the city.', [], 'meta')];
      det.push(slope);
      for (const x of rep.slice(0, 6)) det.push(S(x.type + ', opened ' + fullDate(x.opened) + ', priority ' + x.priority.toLowerCase() + '.', T));
    } else {
      head = [slope, S(STANDING + ' Slopes are estimated from elevation data.', [], 'meta')];
      if (rep !== null) det.push(S(rep.length + ' open sidewalk or curb reports to the city (311) nearby; data through ' + fullDate(d['311_data_through']) + '.', T, 'claim', [String(rep.length)]));
    }
    if (d.nine_in_ten_sections_at_or_below_percent !== null && d.nine_in_ten_sections_at_or_below_percent !== undefined) {
      det.push(S('Nine in ten path sections are at or below ' + d.nine_in_ten_sections_at_or_below_percent + '% grade.', T));
    }
    if (d.city_curb_ramps !== null && d.city_curb_ramps !== undefined) det.push(S("The city's curb-ramp map shows " + d.city_curb_ramps + ' curb ramps within ' + d.radius_feet + ' feet.', T));
    else unk.push('curb ramps (no curb-ramp inventory exists for this area)');
    det.push(S(STANDING, [], 'meta'));
    let cards = [];
    const gp = dataOf(res, 'get_place');
    if (gp && gp.data) {
      const arr = (gp.data.getting_there || {}).arrival;
      cards = [cardFor(gp.data, null, ctx, 3)];
      if (arr) det.push(S('Getting there: ' + arr, [gp.data.link_id]));
    }
    return A('answer', head, { details: det, cards, unknown: unk, sources: sourcesOf(cards) });
  }

  const C = { compose, S, clip, fullDate, monthYear, sourceWords, ageWords, distanceText, fmtPhone, factText, pickFacts, cardFor, positive };
  O.composer = C;
  if (typeof module !== 'undefined') module.exports = C;
})(typeof globalThis !== 'undefined' ? globalThis : this);
