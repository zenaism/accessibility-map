'use strict';
// The JavaScript search must reproduce the Python routes in tests/golden_routes_oxford.json.
const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../../src/atlas/web/routing.js');
const { loadGolden, loadJson, SKIP } = require('./helpers.js');

const opts = { skip: SKIP };
const golden = loadGolden();
let G = null;
const graph = () => (G ||= core.loadGraph(loadJson()));

function pathCost(G, nodes, weights) {
  let c = 0;
  for (let i = 0; i + 1 < nodes.length; i++) c += weights[core.edgeBetween(G, nodes[i], nodes[i + 1])];
  return c;
}

for (const pair of golden.pairs) {
  for (const profile of ['wheelchair', 'blind']) {
    test(`${pair.label} [${profile}]`, opts, () => {
      const G = graph();
      const want = pair.results[profile];
      const a = core.snap(G, pair.from[0], pair.from[1]);
      const b = core.snap(G, pair.to[0], pair.to[1]);
      if (want.reason === 'too_far') {
        assert.ok(a === null || b === null, 'a point should be refused as too far from the network');
        return;
      }
      assert.ok(a && b, 'both points snap');
      const found = core.findPath(G, a.node, b.node, profile);
      if (want.reason === 'no_step_free_route') {
        assert.equal(found, null);
        return;
      }
      assert.ok(found, 'a route exists');
      assert.equal(found.nodes[0], want.path[0]);
      assert.equal(found.nodes.at(-1), want.path.at(-1));
      const weights = profile === 'blind' ? G.blind : G.cost;
      if (JSON.stringify(found.nodes) !== JSON.stringify(want.path)) {
        // equal-cost ties may be broken differently by Dijkstra (networkx) and A*; the cost must still match
        const diff = Math.abs(pathCost(G, want.path, weights) - found.cost);
        assert.ok(diff < 1e-6, `different path with different cost (diff ${diff})`);
        console.log(`  note: tie-broken differently: ${pair.label} [${profile}]`);
      } else {
        assert.deepEqual(found.nodes, want.path);
      }
    });
  }
}

test('shortest path may use stairs and is never longer than the easy path', opts, () => {
  const G = graph();
  for (const pair of golden.pairs) {
    const w = pair.results.wheelchair;
    if (!w.path) continue;
    const s = core.shortestPath(G, w.path[0], w.path.at(-1));
    assert.ok(pathCost(G, s.nodes, G.len) <= pathCost(G, w.path, G.len) + 1e-6);
  }
});

test('snap refuses points more than 150 m from the network and finds the nearest node otherwise', opts, () => {
  const G = graph();
  assert.equal(core.snap(G, 39.0, -84.0), null);
  const i = 100;
  const hit = core.snap(G, G.latDeg[i], G.lonDeg[i]);
  assert.equal(hit.node, i);
  assert.ok(hit.dist < 0.01);
});

test('snap agrees with a brute-force nearest search', opts, () => {
  const G = graph();
  let seed = 12345;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let t = 0; t < 300; t++) {
    const k = Math.floor(rnd() * G.n);
    const lat = G.latDeg[k] + (rnd() - 0.5) * 0.002;
    const lon = G.lonDeg[k] + (rnd() - 0.5) * 0.002;
    const px = lon * Math.cos(G.lat0) * 111320;
    const py = lat * 111320;
    let best = -1;
    let bd = Infinity;
    for (let i = 0; i < G.n; i++) {
      const d = Math.hypot(G.x[i] - px, G.y[i] - py);
      if (d < bd) [best, bd] = [i, d];
    }
    const got = core.snap(G, lat, lon);
    if (bd > 150) assert.equal(got, null);
    else assert.equal(got.node, best);
  }
});

test('a zero-length edge (seen in Cincinnati) does not break the search heuristic', () => {
  // four nodes in a row, ~111 m apart, with a zero-length edge in the middle
  const g = core.loadGraph({
    scale: 1e7,
    lat0: 0.68,
    classes: [],
    flags: {},
    names: [],
    kinds: [],
    nodes: { lon: [0, 0, 0, 0], lat: [0, 10000, 0, 10000] }, // 0, .001, .001, .002 degrees
    edges: {
      u: [0, 1, 2],
      v: [1, 2, 3],
      len: [111.2, 0, 111.2],
      cost: [111.2, 0, 111.2],
      blind: [111.2, 0, 111.2],
      cls: [1, 1, 1],
      name: [-1, -1, -1],
      kind: [-1, -1, -1],
      flags: [0, 0, 0],
      grade: [null, null, null],
    },
  });
  assert.ok(Number.isFinite(g.ratio.wheelchair) && Number.isFinite(g.ratio.blind));
  const p = core.findPath(g, 0, 3, 'wheelchair');
  assert.deepEqual(p.nodes, [0, 1, 2, 3]);
});
