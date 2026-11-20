/* Openway Assistant: rules planner (port of planner.py). Question + context -> plan. Deterministic, no model. */
(function (g) {
  'use strict';
  const O = (g.Openway = g.Openway || {});
  const X = g.Openway.text || require('./text.js');
  const D = g.Openway.dates || require('./dates.js');
  const { norm, tokens, has, hasAny, stem, tokMatch } = X;
  const RATING_ORDER = { accessible: 0, partial: 1, not_accessible: 2, unknown: 3 };
  const R = () => O.rules;

  function mkPlan(intent, f) {
    return Object.assign({
      intent, tool: null, args: {}, need: null, place_type: null, place: null, region: null, when: null, anchor: null,
      clarify: null, topic: null, access: [], unmatched: [], unsupported: [], source: 'rules',
    }, f || {});
  }

  function Index(places) {
    const r = R();
    this.places = places;
    this.generic = new Set(tokens(r.GENERIC_NAME_WORDS.join(' ')).map(stem));
    for (const [, ws] of r.TYPE_WORDS) for (const w of tokens(ws.join(' '))) this.generic.add(stem(w));
    this.byId = new Map(places.map(p => [p.id, p]));
    this.entries = [];
    this.allTokens = new Set();
    const df = {};
    for (const p of places) {
      for (const w of tokens(p.name)) this.allTokens.add(stem(w));
      if (p.layer === 'restroom') continue;
      const main = p.name.split(/[,(]/)[0];
      const toks = X.unique(tokens(main).filter(w => !this.generic.has(stem(w)) && w.length > 1 && !X.isDigits(w)).map(stem));
      for (const w of toks) df[w] = (df[w] || 0) + 1;
      if (toks.length) this.entries.push([p, toks, new Set(tokens(main).map(stem))]);
    }
    this.weight = {};
    for (const w of Object.keys(df)) this.weight[w] = 1 / Math.log(2 + df[w]);
    this.alias = r.ALIASES.map(([a, b]) => [norm(a), norm(b)]);
    this.byName = new Map();
    for (const p of places) if (p.layer !== 'restroom') this.byName.set(norm(p.name), p);
  }
  Index.prototype.resolve = function (t, region) {
    for (const [a, full] of this.alias) if (has(t, a) && this.byName.has(full)) return [this.byName.get(full), 1.0];
    const q = X.unique(t.split(' ').filter(Boolean).map(stem)), qset = new Set(q);
    let best = null;
    for (const [p, toks, allToks] of this.entries) {
      const matched = toks.filter(n => q.some(w => tokMatch(w, n)));
      if (!matched.length) continue;
      const total = toks.reduce((s, n) => s + this.weight[n], 0);
      const got = matched.reduce((s, n) => s + this.weight[n], 0);
      const cov = got / total;
      if (cov < 0.5 || (matched.length < 2 && got < 0.45 && cov < 0.99)) continue;
      let gh = 0;
      for (const x of allToks) if (qset.has(x) && this.generic.has(x)) gh++;
      const key = [-Math.round(cov * 1e6) / 1e6, (region == null || p.region === region) ? 0 : 1, -matched.length, -gh,
        RATING_ORDER[p.rating] === undefined ? 3 : RATING_ORDER[p.rating], p.name.length, p.name];
      if (best === null || X.cmpKeys(key, best[0]) < 0) best = [key, p, cov];
    }
    return best ? [best[1], best[2]] : null;
  };

  function detectRegion(t) {
    const r = R();
    if (has(t, 'oxford')) return 'oxford';
    if (has(t, 'cincinnati') || has(t, 'cincy')) return 'cincinnati';
    for (const region of r.REGION_KEYS) if (hasAny(t, r.REGION_WORDS[region])) return region;
    return null;
  }
  function detectArea(t) {
    let hit = null;
    for (const k of Object.keys(R().AREAS)) {
      if (has(t, k) && (hit === null || norm(k).length > norm(hit[0]).length)) hit = [k, R().AREAS[k]];
    }
    return hit ? hit[1] : null;
  }
  function firstNeed(t) { for (const [need, ws] of R().NEED_WORDS) if (hasAny(t, ws)) return need; return null; }
  function firstType(t) {
    const found = R().TYPE_WORDS.filter(([, ws]) => hasAny(t, ws)).map(x => x[0]);
    const other = found.filter(x => x !== 'restroom');
    return other.length ? other[0] : (found.length ? found[0] : null);
  }
  function contentWords(t, extra) {
    const skip = new Set([...tokens(R().STOP.join(' ')), ...(extra || [])]);
    return t.split(' ').filter(w => w && !skip.has(w) && w.length > 1);
  }
  function capitalized(text, starts) {
    starts = starts || '.?!';
    const out = [], re = /[A-Z][a-zA-Z']+/g;
    let m;
    while ((m = re.exec(text)) !== null) {
      const before = text.slice(0, m.index).replace(/\s+$/, '');
      if (before === '' || starts.includes(before[before.length - 1])) continue;
      out.push(m[0]);
    }
    return out;
  }
  function areaWordSet() {
    const r = R(), words = new Set();
    for (const k of Object.keys(r.AREAS)) for (const w of tokens(k)) words.add(stem(w));
    for (const ws of Object.values(r.REGION_WORDS)) for (const k of ws) for (const w of tokens(k)) words.add(stem(w));
    return words;
  }
  function unmatchedNames(text, index, areaWords, named) {
    const r = R();
    const known = new Set([...areaWords, ...tokens(r.MONTHS_DAYS.concat(r.KNOWN_CAPS).join(' '))]);
    if (named) for (const w of tokens(named.name)) known.add(stem(w));
    const out = [];
    for (const w of capitalized(text)) {
      const tk = stem(norm(w));
      if (tk && !known.has(tk) && !index.generic.has(tk) && tk.length > 2 && !out.includes(tk)) out.push(tk);
    }
    return out;
  }
  function stripPhrases(t, phrases) {
    let out = ' ' + t + ' ';
    for (const p of phrases.slice().sort((a, b) => norm(b).length - norm(a).length || 0)) out = out.split(' ' + norm(p) + ' ').join(' ');
    return out.split(' ').filter(Boolean).join(' ');
  }
  function queryMap(t) {
    for (const [phrases, q] of R().QUERY_MAP) if (hasAny(t, phrases)) return q;
    return null;
  }
  function optionsWhere(text) {
    return [
      { label: 'Use my location', message: text, action: 'locate' },
      { label: 'Downtown Cincinnati', message: text + ' near downtown Cincinnati' },
      { label: 'Uptown Oxford', message: text + ' near uptown Oxford' },
    ];
  }
  const compact = o => { const r = {}; for (const k of Object.keys(o)) if (o[k] !== null && o[k] !== undefined) r[k] = o[k]; return r; };

  function plan(text, ctx, index) {
    const pl = _plan(text, ctx, index);
    if (['nearest', 'search', 'place', 'events', 'area'].includes(pl.intent)) {
      const t = norm(text);
      pl.unsupported = R().UNSUPPORTED.filter(p => has(t, p));
    }
    return pl;
  }

  function _plan(text, ctx, index) {
    const r = R();
    const t = norm(text);
    const region = detectRegion(t) || ctx.region || null;
    const needs = ctx.needs || {};
    if (hasAny(t, r.EMERGENCY) || (has(t, r.EMERGENCY_SOFT) && !hasAny(t, r.EMERGENCY_SOFT_NOT))) return mkPlan('emergency');
    if (hasAny(t, r.HELP) && t.split(' ').length <= 8 && !firstNeed(t) && !firstType(t)) return mkPlan('help');

    const tPlaces = stripPhrases(t, Object.keys(r.AREAS).concat(['oxford', 'cincinnati', 'cincy']));
    const hit = index.resolve(tPlaces, region);
    const named = hit ? hit[0] : null, cov = hit ? hit[1] : 0.0;
    const placeRef = named ? { id: named.id, name: named.name } : null;
    const areaWords = areaWordSet();
    const unmatched = named ? unmatchedNames(text, index, areaWords, named) : [];

    for (const intent of ['ada_trust', 'conflict_trust', 'reports_trust', 'dates_trust']) {
      if (hasAny(t, r.TRUST[intent])) {
        if (intent === 'dates_trust' && hasAny(t, r.EVENT_STRONG)) break;
        const pl = mkPlan(intent, { region, place: placeRef });
        if (named) { pl.tool = 'get_place'; pl.args = { name_or_id: named.id }; }
        return pl;
      }
    }
    const other = hasAny(t, r.OTHER_PLACES);
    if (other && !(has(t, 'oxford') || has(t, 'cincinnati') || has(t, 'cincy'))) return mkPlan('out_of_area', { topic: titleCase(other) });
    for (const cat of r.NO_DATA) if (hasAny(t, cat.words) && !named) return mkPlan('no_data', { topic: cat.label, region });
    if (hasAny(t, r.LIVE_INFO)) {
      let topic = 'that';
      for (const [lab, ph] of r.LIVE_TOPICS) if (hasAny(t, ph)) { topic = lab; break; }
      return mkPlan('live_info', { region, topic, place: placeRef, tool: named ? 'get_place' : null, args: named ? { name_or_id: named.id } : {} });
    }

    const when = D.parseWhen(text, ctx.today);
    const area = detectArea(t);
    const need = firstNeed(t);
    const tType = named ? stripPhrases(t, [named.name].concat(tokens(named.name))) : t;
    const ptype = firstType(tType);
    let access = Object.keys(r.EVENT_ACCESS).filter(k => hasAny(t, r.EVENT_ACCESS[k]));
    if (hasAny(t, r.EVENT_ACCESS_ALL)) access = ['audio_description', 'asl', 'sensory_friendly'];
    let qfirst = null;
    for (const [phrases, q] of r.QUERY_MAP.slice(0, r.QUERY_FIRST)) if (hasAny(t, phrases)) { qfirst = q; break; }
    if (qfirst && !named) {
      const a = { query: qfirst }; if (region) a.region = region; a.limit = 5;
      return mkPlan('search', { tool: 'search_places', args: a, region });
    }

    const strong = hasAny(t, r.EVENT_STRONG), weak = hasAny(t, r.EVENT_WORDS);
    if (strong || (weak && !named && (when || !(need || ptype)))) {
      let words = contentWords(t, r.EVENT_FILLER);
      const evNamed = cov >= 0.99 ? named : null;
      if (evNamed) { const drop = new Set(tokens(evNamed.name).map(stem)); words = words.filter(w => !drop.has(stem(w))); }
      words = words.filter(w => !areaWords.has(stem(w)));
      const w = when || D.defaultRange(ctx.today);
      const args = { start: w.start, end: w.end };
      if (region) args.region = region;
      if (access.length) args.access = access;
      if (hasAny(t, r.EVENT_DISABILITY) && !hasAny(t, r.EVENT_ACCESS_ALL)) args.disability_focused = true;
      if (evNamed) args.link_id = evNamed.id;
      else if (words.length && !access.length) args.query = words.slice(0, 3).join(' ');
      return mkPlan('events', { tool: 'find_events', args, region, when, access, place: evNamed ? placeRef : null });
    }

    if (hasAny(t, r.ROUTE_WORDS)) {
      if (!named) return mkPlan('clarify', { region, clarify: { question: 'Which place do you want to go to?', options: [] } });
      const blind = ['cane', 'guide'].includes(needs.mobility) || (needs.rely || []).includes('screen_reader');
      const args = { to: named.id, profile: blind ? 'blind' : 'wheelchair' };
      if (ctx.location) { args.from_lat = ctx.location[0]; args.from_lon = ctx.location[1]; }
      return mkPlan('route', { tool: 'accessible_route', args, region: region || named.region, place: placeRef });
    }

    if (hasAny(t, r.AREA_WORDS) && !(need && need !== 'step_free_entrance')) {
      const topic = hasAny(t, ['closure', 'closures', 'construction', '311', 'road work', 'sidewalk problems', 'sidewalk closures']) ? 'reports' : 'slope';
      if (named && named.lat !== null && named.lat !== undefined) {
        return mkPlan('area', { tool: 'area_conditions', topic, args: { lat: named.lat, lon: named.lon, region: named.region },
          anchor: { name: named.name, lat: named.lat, lon: named.lon, id: named.id }, place: placeRef, region: named.region });
      }
      let a = area;
      if (a === null && ctx.location) a = { name: 'your location', lat: ctx.location[0], lon: ctx.location[1], region };
      if (a === null && region) a = r.AREAS[region === 'oxford' ? 'uptown oxford' : 'downtown'];
      if (a === null) return mkPlan('clarify', { region, clarify: { question: 'Which area do you mean?', options: optionsWhere(text) } });
      return mkPlan('area', { tool: 'area_conditions', topic, args: { lat: a.lat, lon: a.lon, region: a.region || region },
        anchor: { name: a.name, lat: a.lat, lon: a.lon }, region: a.region || region });
    }

    const nearPhrase = hasAny(t, r.NEAR_WORDS) || hasAny(t, r.NEAR_ME);
    if ((need || ptype || qfirst) && !(named && !nearPhrase)) {
      const steps = needs.steps === 'cannot';
      let eff = need;
      if ((!eff || eff === 'listed_wheelchair_accessible') && steps && ptype !== 'restroom') eff = 'step_free_entrance';
      if (!eff && ptype && r.TYPE_DEFAULT_NEED[ptype]) eff = r.TYPE_DEFAULT_NEED[ptype];
      if (ptype === 'restroom' && !eff) eff = 'accessible_restroom';
      if (eff === 'listed_wheelchair_accessible' && ptype && !['food_drink', 'restroom'].includes(ptype)) eff = null;
      const useType = ptype === 'restroom' ? null : ptype;
      let anchor = null;
      if (named && named.lat !== null && named.lat !== undefined) anchor = { name: named.name, lat: named.lat, lon: named.lon };
      if (anchor === null && area) anchor = { name: area.name, lat: area.lat, lon: area.lon };
      const wantsNear = !!hasAny(t, r.NEAR_ME);
      if (anchor === null && ctx.location && (wantsNear || region === null)) anchor = { name: 'your location', lat: ctx.location[0], lon: ctx.location[1] };
      const nearish = ['accessible_restroom', 'adult_changing_table', 'accessible_parking'].includes(eff) || useType === 'food_drink';
      if (anchor === null && wantsNear && region === null && nearish) {
        return mkPlan('clarify', { need: eff, place_type: useType, region, clarify: { question: 'Where are you? I use your location only to sort places by distance.', options: optionsWhere(text) } });
      }
      if (anchor !== null && (eff || useType) && !qfirst) {
        return mkPlan('nearest', { tool: 'nearest', args: { lat: anchor.lat, lon: anchor.lon, need: eff, place_type: useType, max_miles: 5.0, limit: 5 },
          need: eff, place_type: useType, anchor, region, place: placeRef });
      }
      let q = queryMap(t);
      if (!q && !named) { const miss = unmatchedNames(text, index, areaWords, null); q = miss.length ? miss.join(' ') : null; }
      const args = compact({ region, place_type: useType, need: eff, limit: 5, query: q });
      return mkPlan('search', { tool: 'search_places', args, need: eff, place_type: useType, region });
    }

    if (named) return mkPlan('place', { tool: 'get_place', args: { name_or_id: named.id }, need, place: placeRef, region: region || named.region, unmatched });

    const q = queryMap(t);
    if (q) { const a = { query: q }; if (region) a.region = region; a.limit = 5; return mkPlan('search', { tool: 'search_places', args: a, region }); }
    const miss = unmatchedNames(text, index, areaWords, null);
    const words = miss.length ? miss : contentWords(t, []);
    if (words.length) {
      const a = { query: words.slice(0, 4).join(' ') }; if (region) a.region = region; a.limit = 5;
      return mkPlan('search', { tool: 'search_places', args: a, region, topic: 'words' });
    }
    return mkPlan('unknown', { region });
  }
  function titleCase(s) { return s.replace(/\w\S*/g, w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()); }

  const P = { Index, plan, mkPlan, capitalized, detectRegion, detectArea, firstNeed, firstType, unmatchedNames, areaWordSet, optionsWhere };
  O.planner = P;
  if (typeof module !== 'undefined') module.exports = P;
})(typeof globalThis !== 'undefined' ? globalThis : this);
