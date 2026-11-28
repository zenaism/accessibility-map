'use strict';
// Measures the browser router's A* against plain Dijkstra (A* with a zero heuristic) on the golden Oxford routes.
// Read-only on the project: it loads src/atlas/web/routing.js as text, makes an in-memory copy with two edits
// (a counter on heap pops, and exporting the internal astar function) and runs that copy. Nothing is written
// into the repo.
//
//   node report/search_bench.js <repo> > report/results/search_bench.json
const fs = require('fs');
const path = require('path');

const repo = process.argv[2];
if (!repo) {
  console.error('usage: node search_bench.js <repo checkout of the submission branch>');
  process.exit(1);
}
let src = fs.readFileSync(path.join(repo, 'src/atlas/web/routing.js'), 'utf8');
const before = src;
src = src.replace('if (i === b) break;', 'globalThis.__POPS = (globalThis.__POPS || 0) + 1; if (i === b) break;');
src = src.replace('return { MAX_SNAP_M,', 'return { astar, MAX_SNAP_M,');
if (src === before || !src.includes('astar, MAX_SNAP_M') || !src.includes('__POPS')) {
  console.error('routing.js no longer matches the two patch points; update this script');
  process.exit(1);
}
const m = { exports: {} };
new Function('module', 'self', src)(m, undefined);
const core = m.exports;

const golden = JSON.parse(fs.readFileSync(path.join(repo, 'tests/golden_routes_oxford.json'), 'utf8'));
const t0 = performance.now();
const graphJson = JSON.parse(fs.readFileSync(path.join(repo, 'data/map/routing/oxford.graph.json'), 'utf8'));
const t1 = performance.now();
const G = core.loadGraph(graphJson);
const t2 = performance.now();

function timed(fn, reps) {
  const ts = [];
  let r;
  let pops = 0;
  for (let i = 0; i < reps; i++) {
    globalThis.__POPS = 0;
    const s = performance.now();
    r = fn();
    ts.push(performance.now() - s);
    pops = globalThis.__POPS;
  }
  ts.sort((a, b) => a - b);
  return { r, ms: ts[Math.floor(ts.length / 2)], pops };
}

const rows = [];
for (const pair of golden.pairs) {
  const a = core.snap(G, pair.from[0], pair.from[1]);
  const b = core.snap(G, pair.to[0], pair.to[1]);
  if (!a || !b || a.node === b.node) continue;
  for (const profile of ['wheelchair', 'blind']) {
    const w = profile === 'blind' ? G.blind : G.cost;
    const ratio = profile === 'blind' ? G.ratio.blind : G.ratio.wheelchair;
    const A = timed(() => core.astar(G, a.node, b.node, w, ratio), 15);
    const D = timed(() => core.astar(G, a.node, b.node, w, 0), 15);
    if (!A.r || !D.r) {
      rows.push({ label: pair.label, profile, found: false });
      continue;
    }
    rows.push({
      label: pair.label,
      profile,
      found: true,
      astar_cost: A.r.cost,
      dijkstra_cost: D.r.cost,
      same_cost: Math.abs(A.r.cost - D.r.cost) < 1e-6,
      same_path: JSON.stringify(A.r.nodes) === JSON.stringify(D.r.nodes),
      astar_pops: A.pops,
      dijkstra_pops: D.pops,
      astar_ms: A.ms,
      dijkstra_ms: D.ms,
    });
  }
}
console.log(
  JSON.stringify(
    {
      node_version: process.version,
      nodes: G.n,
      edges: G.m,
      heuristic_ratio: G.ratio,
      json_read_parse_ms: t1 - t0,
      load_graph_ms: t2 - t1,
      rows,
    },
    null,
    1
  )
);
