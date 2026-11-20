/* Route search for the Accessibility Map: load the exported walking network, snap points to it, search.
 *
 * Plain functions with no map or page code, so the same file runs in Node tests, in the page and in a
 * Web Worker. All rules (penalties) are computed in Python and arrive as cost / blind per edge;
 * this file only searches. See src/atlas/export_routing.py for the file format.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.AtlasRoutingCore = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const M_PER_DEG = 111320; // the projection routing.py uses
  const MAX_SNAP_M = 150; // refuse points farther than this from a mapped path (same as Python)
  const CELL_M = 100;

  /** Turn the parsed JSON into typed arrays, an adjacency list (CSR) and a grid index. */
  function loadGraph(j) {
    const n = j.nodes.lon.length;
    const lonDeg = new Float64Array(n);
    const latDeg = new Float64Array(n);
    let a = 0;
    let b = 0;
    for (let i = 0; i < n; i++) {
      a += j.nodes.lon[i];
      b += j.nodes.lat[i];
      lonDeg[i] = a / j.scale;
      latDeg[i] = b / j.scale;
    }
    const cos0 = Math.cos(j.lat0);
    const x = new Float64Array(n);
    const y = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      x[i] = lonDeg[i] * cos0 * M_PER_DEG;
      y[i] = latDeg[i] * M_PER_DEG;
    }
    const E = j.edges;
    const m = E.u.length;
    const cost = new Float64Array(m);
    const blind = new Float64Array(m);
    let ratioW = Infinity;
    let ratioB = Infinity;
    for (let i = 0; i < m; i++) {
      cost[i] = E.cost[i] === null ? Infinity : E.cost[i];
      blind[i] = E.blind[i] === null ? Infinity : E.blind[i];
      if (isFinite(cost[i]) && E.len[i] > 0) {
        // (zero-length edges exist in some networks; 0/0 would make the heuristic NaN)
        ratioW = Math.min(ratioW, cost[i] / E.len[i]);
        ratioB = Math.min(ratioB, blind[i] / E.len[i]);
      }
    }
    if (!isFinite(ratioW)) ratioW = 0;
    if (!isFinite(ratioB)) ratioB = 0;
    const u = Int32Array.from(E.u);
    const v = Int32Array.from(E.v);
    // adjacency in compressed form: edges of node i are adjEdge[adjStart[i] .. adjStart[i+1])
    const adjStart = new Int32Array(n + 1);
    for (let i = 0; i < m; i++) {
      adjStart[u[i] + 1]++;
      adjStart[v[i] + 1]++;
    }
    for (let i = 0; i < n; i++) adjStart[i + 1] += adjStart[i];
    const fill = adjStart.slice(0, n);
    const adjEdge = new Int32Array(2 * m);
    for (let i = 0; i < m; i++) {
      adjEdge[fill[u[i]]++] = i;
      adjEdge[fill[v[i]]++] = i;
    }
    const G = {
      n,
      m,
      scale: j.scale,
      lat0: j.lat0,
      lonDeg,
      latDeg,
      x,
      y,
      u,
      v,
      len: Float64Array.from(E.len),
      cost,
      blind,
      cls: Uint8Array.from(E.cls),
      flags: Uint8Array.from(E.flags),
      nameIdx: Int32Array.from(E.name),
      kindIdx: Int32Array.from(E.kind),
      grade: E.grade,
      names: j.names,
      kinds: j.kinds,
      classes: j.classes,
      FLAGS: j.flags,
      adjStart,
      adjEdge,
      ratio: { wheelchair: ratioW, blind: ratioB, shortest: 1 },
    };
    buildGrid(G);
    return G;
  }

  function buildGrid(G) {
    let x0 = Infinity;
    let y0 = Infinity;
    let x1 = -Infinity;
    let y1 = -Infinity;
    for (let i = 0; i < G.n; i++) {
      x0 = Math.min(x0, G.x[i]);
      x1 = Math.max(x1, G.x[i]);
      y0 = Math.min(y0, G.y[i]);
      y1 = Math.max(y1, G.y[i]);
    }
    const w = Math.max(1, Math.floor((x1 - x0) / CELL_M) + 1);
    const h = Math.max(1, Math.floor((y1 - y0) / CELL_M) + 1);
    const start = new Int32Array(w * h + 1);
    const cell = new Int32Array(G.n);
    for (let i = 0; i < G.n; i++) {
      cell[i] = Math.floor((G.y[i] - y0) / CELL_M) * w + Math.floor((G.x[i] - x0) / CELL_M);
      start[cell[i] + 1]++;
    }
    for (let i = 0; i < w * h; i++) start[i + 1] += start[i];
    const fill = start.slice(0, w * h);
    const items = new Int32Array(G.n);
    for (let i = 0; i < G.n; i++) items[fill[cell[i]]++] = i;
    G.grid = { x0, y0, w, h, start, items };
  }

  /** Nearest graph node to a point. Returns {node, dist} (metres) or null when none is within maxM. */
  function snap(G, lat, lon, maxM) {
    const limit = maxM === undefined ? MAX_SNAP_M : maxM;
    const px = lon * Math.cos(G.lat0) * M_PER_DEG;
    const py = lat * M_PER_DEG;
    const g = G.grid;
    const cx = Math.floor((px - g.x0) / CELL_M);
    const cy = Math.floor((py - g.y0) / CELL_M);
    const maxRing = Math.ceil(limit / CELL_M) + 1;
    let best = -1;
    let bestD = Infinity;
    for (let r = 0; r <= maxRing; r++) {
      for (let gy = cy - r; gy <= cy + r; gy++) {
        if (gy < 0 || gy >= g.h) continue;
        const edgeRow = gy === cy - r || gy === cy + r;
        const step = edgeRow ? 1 : 2 * r || 1;
        for (let gx = cx - r; gx <= cx + r; gx += step) {
          if (gx < 0 || gx >= g.w) continue;
          const c = gy * g.w + gx;
          for (let k = g.start[c]; k < g.start[c + 1]; k++) {
            const i = g.items[k];
            const d = Math.hypot(G.x[i] - px, G.y[i] - py);
            if (d < bestD) {
              bestD = d;
              best = i;
            }
          }
        }
      }
      // every node in ring r+1 is at least r*CELL_M away
      if (best >= 0 && bestD <= r * CELL_M) break;
    }
    return best >= 0 && bestD <= limit ? { node: best, dist: bestD } : null;
  }

  /** A binary min-heap of (priority, node) pairs. */
  class Heap {
    constructor() {
      this.k = [];
      this.v = [];
    }
    get size() {
      return this.k.length;
    }
    push(key, val) {
      const k = this.k;
      const v = this.v;
      let i = k.length;
      k.push(key);
      v.push(val);
      while (i > 0) {
        const p = (i - 1) >> 1;
        if (k[p] <= key) break;
        k[i] = k[p];
        v[i] = v[p];
        i = p;
      }
      k[i] = key;
      v[i] = val;
    }
    pop() {
      const k = this.k;
      const v = this.v;
      const top = v[0];
      const key = k.pop();
      const val = v.pop();
      const n = k.length;
      if (n > 0) {
        let i = 0;
        for (;;) {
          let c = 2 * i + 1;
          if (c >= n) break;
          if (c + 1 < n && k[c + 1] < k[c]) c++;
          if (k[c] >= key) break;
          k[i] = k[c];
          v[i] = v[c];
          i = c;
        }
        k[i] = key;
        v[i] = val;
      }
      return top;
    }
  }

  /** A* from node a to node b on the given per-edge weights. Infinity weight = edge never used.
   *  heuristicRatio: lowest weight/length ratio of any edge, so straight-line distance never overestimates. */
  function astar(G, a, b, weights, heuristicRatio) {
    const dist = new Float64Array(G.n).fill(Infinity);
    const prevNode = new Int32Array(G.n).fill(-1);
    const prevEdge = new Int32Array(G.n).fill(-1);
    const hf = 0.98 * heuristicRatio; // 2% slack: edge lengths are geodesic, the heuristic is flat
    const bx = G.x[b];
    const by = G.y[b];
    const h = (i) => hf * Math.hypot(G.x[i] - bx, G.y[i] - by);
    const heap = new Heap();
    dist[a] = 0;
    heap.push(h(a), a);
    while (heap.size) {
      const i = heap.pop();
      if (i === b) break;
      const di = dist[i];
      for (let k = G.adjStart[i]; k < G.adjStart[i + 1]; k++) {
        const e = G.adjEdge[k];
        const w = weights[e];
        if (w === Infinity) continue;
        const j = G.u[e] === i ? G.v[e] : G.u[e];
        const dj = di + w;
        if (dj < dist[j]) {
          dist[j] = dj;
          prevNode[j] = i;
          prevEdge[j] = e;
          heap.push(dj + h(j), j);
        }
      }
    }
    if (dist[b] === Infinity) return null;
    const nodes = [b];
    const edges = [];
    for (let i = b; i !== a; i = prevNode[i]) {
      edges.push(prevEdge[i]);
      nodes.push(prevNode[i]);
    }
    return { nodes: nodes.reverse(), edges: edges.reverse(), cost: dist[b] };
  }

  /** The cheapest step-free path (profile "wheelchair" or "blind"), or null when there is none. */
  function findPath(G, a, b, profile) {
    const blind = profile === 'blind';
    return astar(G, a, b, blind ? G.blind : G.cost, blind ? G.ratio.blind : G.ratio.wheelchair);
  }

  /** The shortest path by length, stairs allowed (for the "avoids N stairways" comparison). */
  function shortestPath(G, a, b) {
    return astar(G, a, b, G.len, 1);
  }

  /** The edge joining two neighbouring nodes (the network has at most one per pair). */
  function edgeBetween(G, a, b) {
    for (let k = G.adjStart[a]; k < G.adjStart[a + 1]; k++) {
      const e = G.adjEdge[k];
      if ((G.u[e] === a && G.v[e] === b) || (G.u[e] === b && G.v[e] === a)) return e;
    }
    return -1;
  }

  return { MAX_SNAP_M, loadGraph, snap, findPath, shortestPath, edgeBetween };
});
