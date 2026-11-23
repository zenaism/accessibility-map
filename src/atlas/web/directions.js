/* Directions in words: a line-for-line port of the wording code in src/atlas/routing.py
 * (_bearing, _turn, _legs, _feet, _crossing_words, _describe, _summary, _crossing_counts,
 * crossing_sentence and the "compared with the shortest" sentence).
 *
 * Do NOT improve the wording here. Change it in routing.py first, regenerate
 * tests/golden_routes_oxford.json (scripts/make_golden_routes.py), then port the change.
 * tests/js/directions.test.js compares every string with the Python output.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./routing.js'));
  else root.AtlasDirections = factory(root.AtlasRoutingCore);
})(typeof self !== 'undefined' ? self : this, function (core) {
  'use strict';

  const COMPASS = ['north', 'northeast', 'east', 'southeast', 'south', 'southwest', 'west', 'northwest'];
  const FT = 3.28084;
  const CLASS_NAMES = [
    'an unnamed way', // other
    'a footpath', // footway
    'the sidewalk', // footway + sidewalk
    'the crosswalk', // crossing
    'a path',
    'a pedestrian walkway',
    'a service drive',
    'a bike path',
  ];

  // ---- Python number behaviour -------------------------------------------------------------------
  /** Python round(x): to the nearest integer, halves go to the even one. */
  function pyRound(x) {
    const f = Math.floor(x);
    const d = x - f;
    if (d < 0.5) return f;
    if (d > 0.5) return f + 1;
    return f % 2 === 0 ? f : f + 1;
  }
  /** Python round(x, 1). */
  function pyRound1(x) {
    const t = x * 10;
    return pyRound(t) / 10;
  }
  /** Python f"{x:.1f}": toFixed(1), except that exact halves go to the even digit. */
  function fixed1(x) {
    const t = x * 10;
    if (t - Math.floor(t) === 0.5) return (pyRound(t) / 10).toFixed(1);
    return x.toFixed(1);
  }
  /** Python sum() of floats (3.12 and later use compensated summation). */
  function pySum(values) {
    let s = 0;
    let c = 0;
    for (const x of values) {
      const t = s + x;
      if (Math.abs(s) >= Math.abs(x)) c += s - t + x;
      else c += x - t + s;
      s = t;
    }
    return c && isFinite(c) ? s + c : s;
  }
  const radians = (d) => d * (Math.PI / 180);
  const degrees = (r) => r * (180 / Math.PI);
  const capitalize = (s) => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();

  // ---- the port ---------------------------------------------------------------------------------
  function bearing(a, b) {
    const [x1, y1] = a;
    const [x2, y2] = b;
    return (degrees(Math.atan2((x2 - x1) * Math.cos(radians(y1)), y2 - y1)) + 360) % 360;
  }

  function turn(prev, nw) {
    const d = ((nw - prev + 540) % 360) - 180;
    if (Math.abs(d) < 30) return 'continue';
    if (Math.abs(d) > 150) return 'turn around';
    const side = d > 0 ? 'right' : 'left';
    return Math.abs(d) > 60 ? `turn ${side}` : `bear ${side}`;
  }

  /** Edge facts for directions, read from the graph's columns. */
  function edgeInfo(G, e) {
    const F = G.FLAGS;
    const fl = G.flags[e];
    return {
      lengthM: G.len[e],
      name: G.nameIdx[e] >= 0 ? G.names[G.nameIdx[e]] : null,
      cls: G.cls[e],
      grade: G.grade[e],
      steep: !!(fl & F.steep),
      roadNoSidewalk: !!(fl & F.roadNoSidewalk),
      stairs: !!(fl & F.stairs),
      raisedKerb: !!(fl & F.raisedKerb),
      crossing: !!(fl & F.crossing),
      signals: !!(fl & F.signals),
      audible: !!(fl & F.audible),
      tactile: !!(fl & F.tactile),
      kind: G.kindIdx[e] >= 0 ? G.kinds[G.kindIdx[e]] : null,
    };
  }

  /** Group consecutive edges with the same street or path name into legs (routing._legs).
   *  pathXY[i] = [lon, lat] of node i of the path; edges[i] joins path node i and i+1.
   *  Each leg also records fromIdx/toIdx, its first and last path node, so the page can zoom to it. */
  function legsOf(G, pathXY, edges) {
    const legs = [];
    for (let i = 0; i < edges.length; i++) {
      const e = edgeInfo(G, edges[i]);
      let name = e.name || CLASS_NAMES[e.cls];
      if (e.crossing) name = 'the crosswalk';
      const brg = bearing(pathXY[i], pathXY[i + 1]);
      let leg;
      if (legs.length && legs[legs.length - 1].name === name) {
        leg = legs[legs.length - 1];
      } else {
        leg = {
          name,
          length_m: 0.0,
          start_bearing: brg,
          end_bearing: brg,
          steep: 0,
          max_grade: 0.0,
          fromIdx: i,
          toIdx: i,
        };
        legs.push(leg);
      }
      leg.length_m += e.lengthM;
      leg.end_bearing = brg;
      leg.toIdx = i + 1;
      if (e.roadNoSidewalk) leg.road_m = (leg.road_m || 0.0) + e.lengthM;
      if (name === 'the crosswalk') {
        if (!leg.cross) leg.cross = { signals: false, audible: false, tactile: false, kind: null };
        const c = leg.cross;
        c.signals = c.signals || e.signals;
        c.audible = c.audible || e.audible;
        c.tactile = c.tactile || e.tactile;
        c.kind = c.kind || e.kind;
      }
      if (e.grade !== null) {
        leg.max_grade = Math.max(leg.max_grade, e.grade);
        leg.steep += e.steep ? 1 : 0;
      }
    }
    // fold tiny legs (under 8 m) into their neighbours so directions stay readable
    const out = [];
    for (const leg of legs) {
      const last = out[out.length - 1];
      if (last && leg.length_m < 8 && leg.name !== 'the crosswalk') {
        last.length_m += leg.length_m;
        last.end_bearing = leg.end_bearing;
        last.toIdx = leg.toIdx;
        continue;
      }
      if (last && last.name === leg.name) {
        // e.g. two crosswalk pieces in a row
        if (leg.cross) {
          if (!last.cross) last.cross = { ...leg.cross };
          const c = last.cross;
          for (const k of ['signals', 'audible', 'tactile']) c[k] = c[k] || leg.cross[k];
          c.kind = c.kind || leg.cross.kind;
        }
        last.length_m += leg.length_m;
        last.end_bearing = leg.end_bearing;
        last.toIdx = leg.toIdx;
        last.steep += leg.steep;
        last.max_grade = Math.max(last.max_grade, leg.max_grade);
        continue;
      }
      out.push(leg);
    }
    return out;
  }

  function feet(m) {
    const ft = m * FT;
    return ft < 1000 ? `${Math.max(10, pyRound(ft / 10) * 10)} feet` : `${fixed1(ft / 5280)} miles`;
  }

  /** (what to do, details) for a crossing. */
  function crossingWords(c) {
    const extra = c.tactile ? '; tactile paving at the curb' : '';
    if (c.signals) {
      const sig = c.audible ? 'audible signal' : 'no audible signal mapped';
      return ['Cross at the traffic signal', sig + extra];
    }
    const kind = c.kind;
    if (kind === 'marked' || kind === 'zebra' || kind === 'uncontrolled') {
      return ['Cross at the marked crosswalk', 'no signal' + extra];
    }
    if (kind === 'unmarked') return ['Cross at an unmarked crossing', 'no signal' + extra];
    return ['Cross the street', 'crossing type not mapped' + extra];
  }

  /** The steps in words. Same strings as routing._describe. */
  function describe(legs) {
    return describeDetailed(legs).map((s) => s.text);
  }

  /** Like describe(), but each step also says what kind of step it is and which part of the route it covers
   *  (for icons, "Caution" labels and zooming). `text` is exactly the Python string. */
  function describeDetailed(legs) {
    const steps = [];
    for (let i = 0; i < legs.length; i++) {
      const leg = legs[i];
      const heading = COMPASS[pyRound(leg.start_bearing / 45) % 8];
      let s;
      let kind;
      if (leg.name === 'the crosswalk') {
        const [head, detail] = crossingWords(leg.cross || {});
        s = `${head}, ${feet(leg.length_m)} (${detail})`;
        kind = 'cross';
      } else if (i === 0) {
        s = `Head ${heading} on ${leg.name} for ${feet(leg.length_m)}`;
        kind = 'start';
      } else {
        const t = turn(legs[i - 1].end_bearing, leg.start_bearing);
        const verb = t === 'continue' ? 'Continue' : capitalize(t);
        s = `${verb} onto ${leg.name} for ${feet(leg.length_m)}`;
        kind = t === 'continue' ? 'straight' : t.replace(/ /g, '-');
      }
      const warnings = [];
      if ((leg.road_m || 0) > 0.5 * leg.length_m) {
        s += '; no sidewalk mapped here';
        warnings.push('no-sidewalk');
      }
      if (leg.steep) {
        const n = leg.steep;
        s += `; caution: ${n} short section${n > 1 ? 's' : ''} steeper than a ramp`;
        warnings.push('steep');
      }
      if (leg.name === 'the crosswalk') {
        const c = leg.cross || {};
        if (!c.signals) warnings.push('crossing-no-signal');
        else if (!c.audible) warnings.push('crossing-not-audible');
      }
      steps.push({
        text: s + '.',
        kind,
        warnings,
        feet: Math.max(10, pyRound((leg.length_m * FT) / 10) * 10),
        fromIdx: leg.fromIdx,
        toIdx: leg.toIdx,
      });
    }
    return steps;
  }

  const isRoadNoSidewalkFlag = (G, e) => !!(G.flags[e] & G.FLAGS.roadNoSidewalk);

  function summary(G, edges) {
    const es = edges.map((e) => edgeInfo(G, e));
    const grades = es.filter((e) => e.grade !== null);
    return {
      length_m: pyRound1(pySum(es.map((e) => e.lengthM))),
      steep_sections: grades.filter((e) => e.steep).length,
      steps: es.filter((e) => e.stairs).length,
      road_without_sidewalk_m: pyRound1(
        pySum(edges.filter((e) => isRoadNoSidewalkFlag(G, e)).map((e) => G.len[e]))
      ),
      raised_kerbs: es.filter((e) => e.raisedKerb).length,
      crossings: crossingCounts(es),
    };
  }

  /** Count crossings once per street crossed (consecutive crossing edges are one crossing). */
  function crossingCounts(es) {
    const out = { total: 0, signals: 0, audible: 0, marked: 0, unmarked_or_unknown: 0, tactile: 0 };
    let prev = false;
    for (const e of es) {
      const cur = e.crossing;
      if (cur && !prev) {
        out.total += 1;
        const kind = (e.kind || '').toLowerCase();
        if (e.signals || kind === 'traffic_signals') {
          out.signals += 1;
          out.audible += e.audible ? 1 : 0;
        } else if (kind === 'marked' || kind === 'zebra' || kind === 'uncontrolled') {
          out.marked += 1;
        } else {
          out.unmarked_or_unknown += 1;
        }
        out.tactile += e.tactile ? 1 : 0;
      }
      prev = cur;
    }
    return out;
  }

  function crossingSentence(c) {
    if (!c || !c.total) return 'No street crossings.';
    const parts = [];
    if (c.signals) parts.push(`${c.signals} with traffic signals (${c.audible} audible)`);
    if (c.marked) parts.push(`${c.marked} marked without a signal`);
    if (c.unmarked_or_unknown) parts.push(`${c.unmarked_or_unknown} unmarked or not mapped`);
    const n = c.total;
    return `${n} street crossing${n > 1 ? 's' : ''}: ` + parts.join(', ') + '.';
  }

  /** Easiest route between two points with directions in words (routing.route).
   *  Returns {error: 'too_far', which: 'from' | 'to'}, {error: 'no_route'} or the result object
   *  (same keys as Python, plus `nodes`, `edges`, `stepList` and `lineIdx` for the page). */
  function route(G, fromLat, fromLon, toLat, toLon, profile) {
    profile = profile || 'wheelchair';
    const sa = core.snap(G, fromLat, fromLon);
    const sb = core.snap(G, toLat, toLon);
    if (!sa) return { error: 'too_far', which: 'from' };
    if (!sb) return { error: 'too_far', which: 'to' };
    const easy = core.findPath(G, sa.node, sb.node, profile);
    if (!easy) return { error: 'no_route' };
    const short = core.shortestPath(G, sa.node, sb.node);
    const xy = easy.nodes.map((n) => [G.lonDeg[n], G.latDeg[n]]);
    const legs = legsOf(G, xy, easy.edges);
    const sEasy = summary(G, easy.edges);
    const sShort = summary(G, short.edges);
    const extra = sEasy.length_m - sShort.length_m;
    const why = [];
    for (const [key, word] of [
      ['steps', 'stair section'],
      ['steep_sections', 'steep section'],
    ]) {
      const n = sShort[key] - sEasy[key];
      if (n > 0) why.push(`${n} ${word}${n > 1 ? 's' : ''}`);
    }
    const compare =
      extra > 15 && why.length
        ? `About ${feet(extra)} longer than the shortest way, to avoid ` + why.join(' and ') + '.'
        : 'This is also the shortest way.';
    const stepList = describeDetailed(legs);
    return {
      length_feet: pyRound(sEasy.length_m * FT),
      steep_sections: sEasy.steep_sections,
      steps: sEasy.steps,
      raised_kerbs: sEasy.raised_kerbs,
      crossings: sEasy.crossings,
      crossings_text: crossingSentence(sEasy.crossings),
      profile,
      road_without_sidewalk_feet: pyRound(sEasy.road_without_sidewalk_m * FT),
      directions: stepList.map((s) => s.text),
      compared_with_shortest: compare,
      shortest: {
        length_feet: pyRound(sShort.length_m * FT),
        steps: sShort.steps,
        steep_sections: sShort.steep_sections,
      },
      line: xy.map(([lon, lat]) => [pyRound(lon * 1e6) / 1e6, pyRound(lat * 1e6) / 1e6]),
      snap_feet: [pyRound(sa.dist * FT), pyRound(sb.dist * FT)],
      nodes: easy.nodes,
      edges: easy.edges,
      stepList,
    };
  }

  return {
    COMPASS,
    bearing,
    turn,
    legsOf,
    feet,
    crossingWords,
    describe,
    describeDetailed,
    summary,
    crossingCounts,
    crossingSentence,
    route,
    pyRound,
  };
});
