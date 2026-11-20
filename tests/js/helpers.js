'use strict';
// Shared by the JavaScript tests: loads the exported Oxford graph and the golden routes.
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const GRAPH = path.join(ROOT, 'data', 'map', 'routing', 'oxford.graph.json');
const GOLDEN = path.join(ROOT, 'tests', 'golden_routes_oxford.json');

function graphFile() {
  return fs.existsSync(GRAPH) ? GRAPH : null;
}
function loadGolden() {
  return JSON.parse(fs.readFileSync(GOLDEN, 'utf8'));
}
function loadJson() {
  return JSON.parse(fs.readFileSync(GRAPH, 'utf8'));
}
const SKIP = graphFile()
  ? false
  : 'graph not built: run `python -m atlas.export_routing --region oxford` first';

module.exports = { ROOT, loadGolden, loadJson, SKIP };
