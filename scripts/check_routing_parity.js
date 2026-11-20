'use strict';
// node scripts/check_routing_parity.js parity.json   (see check_routing_parity.py)
const fs = require('fs');
const core = require('../src/atlas/web/routing.js');
const D = require('../src/atlas/web/directions.js');
const G = core.loadGraph(JSON.parse(fs.readFileSync(`data/map/routing/${process.env.REGION || 'oxford'}.graph.json`, 'utf8')));
const cases = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
let ok = 0, none = 0, bad = 0;
for (const c of cases) {
  const got = D.route(G, c.from[0], c.from[1], c.to[0], c.to[1], c.profile);
  if (c.result === null) { if (got.error) none++; else { bad++; console.log('expected null', JSON.stringify(c.from)); } continue; }
  if (got.error) { bad++; console.log('unexpected', got.error, JSON.stringify(c.from)); continue; }
  const keys = ['directions', 'length_feet', 'compared_with_shortest', 'crossings_text', 'steep_sections', 'steps', 'road_without_sidewalk_feet', 'raised_kerbs'];
  const diff = keys.filter((k) => JSON.stringify(got[k]) !== JSON.stringify(c.result[k]));
  if (diff.length) { bad++; console.log('DIFF', diff, JSON.stringify(c.from), c.profile); } else ok++;
}
console.log({ matched: ok, bothNull: none, mismatched: bad });
process.exit(bad ? 1 : 0);
