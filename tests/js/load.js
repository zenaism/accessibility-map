// Loads the assistant modules in Node the same way a browser would (shared globalThis.Openway).
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const WEB = path.join(__dirname, '..', '..', 'src', 'atlas', 'web', 'assistant');
const DATA = path.join(__dirname, '..', '..', 'data', 'map', 'assistant');
for (const f of ['text', 'dates', 'tools', 'planner', 'composer', 'verify', 'engine']) require(path.join(WEB, f + '.js'));
const O = globalThis.Openway;
function guided() {
  const rules = JSON.parse(fs.readFileSync(path.join(DATA, 'rules.json'), 'utf8'));
  const files = ['cincinnati', 'oxford'].map(r => JSON.parse(fs.readFileSync(path.join(DATA, r + '.json'), 'utf8')));
  return new O.engine.GuidedEngine(files, rules);
}
module.exports = { O, guided, WEB, DATA };
