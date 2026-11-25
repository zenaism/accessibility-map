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

  // ---- short answers: confidence, shortening, chips (port of the same section in composer.py) ----
  const MAX_WORDS = 25, MAX_LABEL = 28;
  const LONG_OK = ['unknown', 'no_data', 'out_of_area'];
  const ABBREVIATIONS = new Set(['mt', 'st', 'dr', 'ave', 'jr', 'sr', 'no', 'vs', 'ft', 'inc', 'co', 'mr', 'mrs', 'ms']);
  const trimStart = (s, chars) => { let i = 0; while (i < s.length && chars.includes(s[i])) i++; return s.slice(i); };
  const words = t => String(t).split(/\s+/).filter(Boolean);
  const hostOf = url => { const m = String(url || '').toLowerCase().match(/^https?:\/\/(?:www\.)?([^/]+)/); return m ? m[1] : ''; };
  function dateShort(d) {
    if (d.length >= 7 && d[4] === '-' && /^\d\d/.test(d.slice(5, 7)) && parseInt(d.slice(5, 7), 10) >= 1 && parseInt(d.slice(5, 7), 10) <= 12) return D.cap(D.MONTHS[parseInt(d.slice(5, 7), 10) - 1].slice(0, 3)) + ' ' + d.slice(0, 4);
    return d.slice(0, 4);
  }
  const isOld = (d, today) => /^\d{4}/.test(d) && parseInt(today.slice(0, 4), 10) - parseInt(d.slice(0, 4), 10) >= 2;
  function newestFact(fs) { let best = null; for (const f of fs) if (f.date && (best === null || f.date > best.date)) best = f; return best; }
  function cardConfidence(card, need, today) {
    const spec = R().NEEDS[need || ''] || {};
    const attrs = new Set((spec.facts || []).map(factLabel));
    const layerOk = !!spec.restroom_layer && card.type === R().TYPE_LABELS.restroom;
    const pos = f => new Set(R().POSITIVE).has(String(f.value).split(';').pop().trim());
    const general = !need || need === 'listed_wheelchair_accessible';
    let positives = card.facts.filter(f => pos(f) && (!need || attrs.has(f.label) || layerOk));
    if (general && card.rating !== 'accessible') positives = [];
    const line = (best, word) => {
      const host = hostOf(best.source) || 'a listed source';
      if (isOld(best.date, today)) return 'Old record · ' + host + ', ' + best.date.slice(0, 4) + '. May be out of date.';
      return word + ' · ' + host + ', ' + dateShort(best.date);
    };
    if (positives.length) {
      const best = newestFact(positives);
      if (best) return line(best, 'Confirmed');
      return 'Reported · ' + (hostOf(positives[0].source) || 'a listed source') + ', no date';
    }
    if (card.rating === 'unknown') {
      const hosts = new Set(card.facts.filter(f => f.source).map(f => hostOf(f.source)));
      if (hosts.size === 1 && hosts.has('openstreetmap.org')) return 'Not known · OpenStreetMap lists the place, with no access details';
      return 'Not known · no access details in our data';
    }
    const best = newestFact(card.facts);
    if (best) return line(best, 'Reported');
    const src = (card.facts.find(f => f.source) || {}).source || '';
    if (src) return 'Reported · ' + (hostOf(src) || 'a listed source') + ', no date';
    return 'Not known · no access details in our data';
  }
  function newestYear(card) { const ds = card.facts.filter(f => f.date).map(f => f.date); return ds.length ? ds.reduce((a, b) => (b > a ? b : a)).slice(0, 4) : ''; }
  function needWord(need, placeType) {
    const lab = needLabel(need) || R().TYPE_LABELS[placeType || ''] || 'access';
    return lab.replace(/^(an|a) /, '').replace(/^accessible /, '');
  }
  function closerNote(card, need, placeType) {
    const w = needWord(need, placeType);
    if (card.confidence.startsWith('Old record')) return 'Closer, but the ' + w + ' record is from ' + newestYear(card) + ' and may be out of date.';
    if (card.confidence.startsWith('Not known')) return 'Closer, but I have no ' + w + ' details for it.';
    return null;
  }
  function isBoundary(w, nxt) {
    if (!w || !'.!?'.includes(w[w.length - 1]) || !nxt || !(nxt[0] >= 'A' && nxt[0] <= 'Z')) return false;
    if (w[w.length - 1] === '.') {
      const base = trimEnd(w, '.!?').toLowerCase();
      if (base.length === 1 || ABBREVIATIONS.has(base)) return false;
    }
    return true;
  }
  function splitSentences(text) {
    const ws = text.split(' '), out = []; let cur = [];
    ws.forEach((w, i) => { cur.push(w); if (i + 1 < ws.length && isBoundary(w, ws[i + 1])) { out.push(cur.join(' ')); cur = []; } });
    if (cur.length) out.push(cur.join(' '));
    return out;
  }
  const balanced = ws => { const t = ws.join(' '); return t.split('(').length === t.split(')').length; };
  function upperFirst(t) {
    const m = t.match(/\p{L}/u);
    return m ? t.slice(0, m.index) + m[0].toUpperCase() + t.slice(m.index + m[0].length) : t;
  }
  function cutSentence(text, limit) {
    limit = limit || MAX_WORDS;
    const ws = words(text);
    if (ws.length <= limit) return [text, ''];
    let n = 0;
    for (let k = limit; k > 2; k--) if ((ws[k - 1].endsWith(',') || ws[k].startsWith('(')) && balanced(ws.slice(0, k))) { n = k; break; }
    if (!n) { n = limit; for (let k = limit; k > 2; k--) if (balanced(ws.slice(0, k))) { n = k; break; } }
    let head = trimEnd(ws.slice(0, n).join(' '), ',;:');
    if (!'.!?'.includes(head[head.length - 1])) head += '.';
    let rest = upperFirst(trimStart(ws.slice(n).join(' '), ',;: '));
    if (!'.!?…'.includes(rest[rest.length - 1])) rest += '.';
    return [head, rest];
  }
  function shorten(a) {
    const units = [];
    for (const s of a.headline) for (const piece of splitSentences(s.text)) units.push(S(piece, s.refs.slice(), s.kind, s.derived.slice()));
    if (!units.length) return a;
    const two = LONG_OK.includes(a.kind) && units.length >= 2 && words(units[0].text).length + words(units[1].text).length <= MAX_WORDS;
    const keep = two ? 2 : 1;
    let moved = [], kept = units.slice(0, keep);
    if (!two) {
      const [head, rest] = cutSentence(units[0].text);
      if (rest) { const u = units[0]; kept = [S(head, u.refs.slice(), u.kind, u.derived.slice())]; moved.push(S(rest, u.refs.slice(), u.kind, u.derived.slice())); }
    }
    moved = moved.concat(units.slice(keep));
    a.headline = kept;
    a.details = moved.concat(a.details);
    return a;
  }
  const HELP_CHIPS = {
    restroom: ['Restroom near me', 'Where is the closest accessible restroom?'],
    parking: ['Accessible parking', 'Where is accessible parking near me?'],
    food: ['Step-free food', 'Find food with no steps at the door'],
    events: ['Events this week', 'What events are on this week?'],
    trails: ['Paved trails', 'What paved trails are there?'],
  };
  const AT_PLACE = {
    parking: ['Parking at', n => 'Does ' + n + ' have accessible parking?'],
    entrance: ['Entrance at', n => 'Does ' + n + ' have a step-free entrance?'],
    restroom: ['Restroom at', n => 'Does ' + n + ' have an accessible restroom?'],
  };
  const NEED_CATEGORY = { accessible_restroom: 'restroom', accessible_parking: 'parking', step_free_entrance: 'entrance' };
  const TYPE_CATEGORY = { restroom: 'restroom', food_drink: 'food', trail: 'trails' };
  function shortName(name) {
    let n = name.trim().replace(/\s+for the .*$/, '');
    if (words(n).length > 1) n = n.replace(/^The\s+/, '');
    return trimEnd(trimStart(n.trim(), ' ,'), ' ,');
  }
  function placeLabel(prefix, name) {
    const ws = words(shortName(name)).slice(0, 3);
    while (ws.length && ['&', 'and', 'of', 'the', 'for', 'at'].includes(ws[ws.length - 1].toLowerCase())) ws.pop();
    while (ws.length) { const label = prefix + ' ' + ws.join(' '); if (label.length <= MAX_LABEL) return label; ws.pop(); }
    return (prefix + ' there').slice(0, MAX_LABEL);
  }
  const answeredCategory = pl => pl.intent === 'events' ? 'events' : (NEED_CATEGORY[pl.need || ''] || TYPE_CATEGORY[pl.place_type || ''] || null);
  function makeFollowups(a, pl) {
    const done = a.kind === 'answer' ? answeredCategory(pl) : null;
    const chips = [], used = new Set();
    let name = '';
    if (a.kind === 'answer' && a.cards.length && pl.intent !== 'events' && a.cards[0].type !== 'event') { name = a.cards[0].name; if (a.cards[0].type === R().TYPE_LABELS.restroom) name = ''; }
    else if (a.kind === 'answer' && pl.place) name = pl.place.name || '';
    if (name) {
      for (const cat of ['parking', 'entrance', 'restroom']) {
        if (cat === done || chips.length === 2) continue;
        const [prefix, msg] = AT_PLACE[cat];
        chips.push({ label: placeLabel(prefix, name), message: msg(name) });
        used.add(cat);
      }
    }
    for (const cat of ['restroom', 'parking', 'food', 'events', 'trails']) {
      if (chips.length === 3) break;
      if (cat === done || used.has(cat)) continue;
      chips.push({ label: HELP_CHIPS[cat][0], message: HELP_CHIPS[cat][1] });
    }
    for (const t of R().HELP_TILES) {
      if (chips.length === 3) break;
      if (chips.every(c => c.message !== t.message)) chips.push({ label: t.label, message: t.message });
    }
    return chips.slice(0, 3);
  }
  const KIND_CONFIDENCE = {
    unknown: 'Not known · nothing in our data answers this',
    no_data: 'Not known · we have no data on this topic yet',
    out_of_area: 'Not known · outside Cincinnati and Oxford',
  };
  function answerConfidence(a, pl) {
    if (KIND_CONFIDENCE[a.kind]) return KIND_CONFIDENCE[a.kind];
    if (a.kind !== 'answer') return 'Guide · not a data answer';
    if (pl.intent.endsWith('_trust')) return 'Guide · not a data answer';
    if (pl.intent === 'route' || pl.intent === 'area') return 'Computed · map data, not checked on site';
    if (a.cards.length && a.cards[0].confidence) return a.cards[0].confidence;
    return 'Guide · not a data answer';
  }
  function finish(a, pl) {
    shorten(a);
    a.cards.forEach((c, i) => { c.lead = i === 0; });
    a.confidence = answerConfidence(a, pl);
    a.followups = makeFollowups(a, pl);
    return a;
  }

  function cardFor(row, need, ctx, k) {
    const facts = pickFacts(row.facts || [], need, k === undefined ? 4 : k);
    const seen = new Set(), sources = [];
    for (const f of facts) {
      const key = f.source || '';
      if (key && !seen.has(key)) { seen.add(key); sources.push({ url: key, date: f.date || '', quote: f.quote || '', label: sourceWords(key) }); }
    }
    const m = row.miles === undefined ? null : row.miles;
    const card = {
      place_id: row.link_id, name: row.name, type: R().TYPE_LABELS[row.type] || row.type || '', rating: row.rating,
      facts: facts.map(f => toFact(f, row.link_id)), sources, miles: m, direction: row.direction === undefined ? null : row.direction,
      distance_text: distanceText(m), phone: fmtPhone(row.phone) || null, note: row.notice || null,
      lat: row.lat === undefined ? null : row.lat, lon: row.lon === undefined ? null : row.lon, event: null,
      confidence: '', lead: false,
    };
    card.confidence = cardConfidence(card, need, ctx.today);
    return card;
  }
  function eventCard(e, ctx, asOf) {
    return {
      place_id: e.link_id, name: e.place, type: 'event', rating: e.rating, facts: [],
      sources: e.url ? [{ url: e.url, date: '', quote: '', label: sourceWords(e.url) }] : [],
      miles: null, direction: null, distance_text: null, phone: null, note: null, lat: null, lon: null,
      event: { title: e.title, start: e.start, when_text: D.whenText(e.start), url: e.url || '', access: (e.access || []).map(a => R().ACCESS_WORDS[a] || a) },
      confidence: 'Reported · ' + (hostOf(e.url) || 'event listing') + ', ' + dateShort(asOf || ctx.today), lead: false,
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
      clarify: null, as_of: null, notes: [], verified: false, removed: 0, plan: null, engine: 'rules', confidence: '', followups: [],
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
    return finish(a, pl);
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
    let rows = (r && r.data) || [];
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
    // the nearest card with a confirmed, recent record leads; closer cards with old or unknown records get a note
    const allCards = rows.map(x => cardFor(x, need, ctx));
    let leadI = allCards.findIndex(c => c.confidence.startsWith('Confirmed'));
    if (leadI < 0) leadI = 0;
    const confirmed = allCards[leadI].confidence.startsWith('Confirmed');
    const order = [leadI].concat(rows.map((_, i) => i).filter(i => i !== leadI));
    for (let i = 0; i < leadI; i++) {
      const note = closerNote(allCards[i], pl.need, pl.place_type);
      if (note) { const c = allCards[i]; c.note = c.note ? c.note + '. ' + note : note; }
    }
    const cards = order.map(i => allCards[i]).slice(0, MAX_CARDS);
    rows = order.map(i => rows[i]);
    const first = rows[0], nm = first.name, refs = [first.link_id];
    let lead;
    if (pl.intent === 'nearest' && first.miles !== undefined && first.miles !== null) {
      const anchorT = pl.anchor.name === 'your location' ? 'you' : pl.anchor.name;
      const of = cards[0].distance_text + ' ' + first.direction + ' of ' + anchorT;
      if (confirmed) lead = 'The closest one I can confirm is ' + nm + ', ' + of + '.';
      else lead = pl.need ? 'The closest place I found with ' + ask + ' is ' + nm + ', ' + of + '.' : 'The closest ' + (ask || 'place') + ' I found is ' + nm + ', ' + of + '.';
      if (pl.anchor.name === nm) lead = pl.need ? nm + ' itself has ' + ask + ' on record.' : nm + ' itself is the closest.';
      if (plain) lead = confirmed ? 'Closest I can confirm: ' + nm + ', ' + of + '.' : (pl.need ? 'Closest with ' + ask + ': ' + nm + ', ' + of + '.' : 'Closest: ' + nm + ', ' + of + '.');
    } else {
      const pick = confirmed ? 'the first I can confirm is' : 'the first is';
      if (pl.need) lead = rows.length > 1 ? rows.length + ' places have ' + ask + ' on record; ' + pick + ' ' + nm + '.' : 'One place has ' + ask + ' on record: ' + nm + '.';
      else lead = rows.length > 1 ? 'I found ' + rows.length + ' places that match; ' + pick + ' ' + nm + '.' : 'I found one place that matches: ' + nm + '.';
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
        const cards = nrows.slice(0, MAX_CARDS).map(x => eventCard(x, ctx, asOf));
        return A('unknown', head, { details: [snap], cards, unknown: ['events in that time'], sources: sourcesOf(cards) });
      }
      head.push(snap);
      return A('unknown', head, { unknown: ['events in that time'] });
    }
    const e = rows[0];
    const s1 = rows.length > 1 ? 'I found ' + rows.length + ' ' + adj + 'events ' + label + '; the first is ' + e.title + ', ' + D.whenText(e.start) + ', at ' + e.place + '.'
      : 'I found one ' + adj + 'event ' + label + ': ' + e.title + ', ' + D.whenText(e.start) + ', at ' + e.place + '.';
    const head = [S(s1, [e.link_id], 'claim', [String(rows.length)]), snap];
    const cards = rows.slice(0, MAX_CARDS).map(x => eventCard(x, ctx, asOf));
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

  const C = { compose, finish, shorten, splitSentences, cutSentence, cardConfidence, S, clip, fullDate, monthYear, sourceWords, ageWords, distanceText, fmtPhone, factText, pickFacts, cardFor, positive };
  O.composer = C;
  if (typeof module !== 'undefined') module.exports = C;
})(typeof globalThis !== 'undefined' ? globalThis : this);
