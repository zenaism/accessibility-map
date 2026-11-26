'use strict';
// The spoken wording of route steps and the voice controller's fallback rules (no browser needed).
const test = require('node:test');
const assert = require('node:assert/strict');
const V = require('../../src/atlas/web/map/voice.js');
const W = V.words;
const S = (text) => ({ text });

test('a plain step is said as written, with a final full stop', () => {
  assert.equal(W.step(S('Turn right onto the Weeb Ewbank Way sidewalk for 780 feet.')), 'Turn right onto the Weeb Ewbank Way sidewalk for 780 feet.');
});
test('a crossing says its detail as a separate short sentence', () => {
  assert.equal(W.step(S('Cross at the marked crosswalk, 40 feet (no signal).')), 'Cross at the marked crosswalk, 40 feet. No signal.');
  assert.equal(W.step(S('Cross at the traffic signal, 40 feet (no audible signal mapped).')), 'Cross at the traffic signal, 40 feet. No audible signal mapped.');
});
test('warnings after a semicolon become their own sentences', () => {
  assert.equal(W.step(S('Head southwest on Weeb Ewbank Way for 950 feet; no sidewalk mapped here.')), 'Head southwest on Weeb Ewbank Way for 950 feet. No sidewalk mapped here.');
  assert.equal(W.step(S('Continue onto a footpath for 0.2 miles; caution: 2 short sections steeper than a ramp.')), 'Continue onto a footpath for 0.2 miles. Caution: 2 short sections steeper than a ramp.');
});
test('the heads-up gives the distance first and drops the length of the next step', () => {
  assert.equal(W.ahead(S('Turn left onto the East Chestnut Street sidewalk for 910 feet.'), 100), 'In 100 feet, turn left onto the East Chestnut Street sidewalk.');
  assert.equal(W.ahead(S('Cross at the marked crosswalk, 40 feet (no signal).'), 96), 'In 100 feet, cross at the marked crosswalk. No signal.');
  assert.equal(W.ahead(S('Continue onto a footpath for 0.2 miles.'), 3), 'In 10 feet, continue onto a footpath.');
});
test('start and arrival', () => {
  assert.equal(W.start(S('Head north on High Street for 300 feet.')), 'Route started. Head north on High Street for 300 feet.');
  assert.equal(W.arrive('Armstrong Student Center'), 'You have arrived at Armstrong Student Center.');
  assert.equal(W.arrive(''), 'You have arrived.');
});
test('every step of the Oxford golden routes can be said and ends with one full stop', () => {
  const g = JSON.parse(require('node:fs').readFileSync(require('node:path').join(__dirname, '..', 'golden_routes_oxford.json'), 'utf8'));
  let n = 0;
  for (const p of g.pairs) for (const prof of ['wheelchair', 'blind']) {
    const r = p.results[prof].result; if (!r) continue;
    for (const d of r.directions) { const s = W.step(S(d)), a = W.ahead(S(d), 100); n++; assert.match(s, /[^.]\.$/); assert.match(a, /^In 100 feet, [a-z].*[^.]\.$/); assert.ok(!/[()]/.test(s + a), s); }
  }
  assert.ok(n > 20);
});

// ---- controller with fake speech
function fake({ voices = [{ name: 'Samantha', lang: 'en-US', localService: true }], Worker } = {}) {
  const said = [];
  const store = {}; 
  const win = {
    speechSynthesis: { speak: (u) => said.push(u.text), cancel() {}, getVoices: () => voices },
    SpeechSynthesisUtterance: function (t) { this.text = t; },
    localStorage: { getItem: (k) => store[k] || null, setItem: (k, v) => { store[k] = v; } },
    location: { href: 'http://x.test/map/oxford.html' }, Worker,
  };
  return { win, said, store };
}
test('voice is off by default and says nothing until turned on', () => {
  const f = fake(); const c = V.create({ window: f.win });
  assert.equal(c.isOn(), false); c.speak('Hello.'); assert.deepEqual(f.said, []);
  c.setOn(true); c.speak('Hello.'); assert.deepEqual(f.said.filter((t) => t.trim()), ['Hello.']);
});
test('the choices are kept on the device and survive a reload', () => {
  const f = fake(); const c = V.create({ window: f.win }); c.setOn(true); c.setSpeed('fast');
  const d = V.create({ window: f.win }); assert.equal(d.isOn(), true); assert.equal(d.state.prefs.speed, 'fast');
});
test('repeat says the last line again, or the fallback, even when voice is off', () => {
  const f = fake(); const c = V.create({ window: f.win });
  assert.equal(c.repeat(''), false);
  assert.equal(c.repeat('Turn left.'), true); assert.equal(f.said.at(-1), 'Turn left.'); assert.equal(c.isOn(), false);
});
test('the natural voice falls back to the device voice when its files cannot load', () => {
  let w; const Worker = function () { w = this; this.postMessage = () => {}; this.terminate = () => {}; };
  const f = fake({ Worker }); const c = V.create({ window: f.win }); c.setOn(true); c.setNatural(true);
  assert.equal(c.state.natural, 'loading');
  c.speak('Turn right.'); assert.equal(f.said.at(-1), 'Turn right.');          // still loading: the device voice speaks
  w.onmessage({ data: { type: 'error', message: 'HTTP 404' } });
  assert.equal(c.state.natural, 'failed'); assert.equal(c.state.prefs.natural, false);
  c.speak('Cross now.'); assert.equal(f.said.at(-1), 'Cross now.');
});
test('with no speech support at all, speaking reports false and nothing throws', () => {
  const f = fake(); f.win.speechSynthesis = null; const c = V.create({ window: f.win }); c.setOn(true);
  assert.equal(c.supported(), false); assert.equal(c.speak('x'), false);
});
test('the best device voice is a natural English one, not a novelty voice', () => {
  const list = [{ name: 'Fred', lang: 'en-US', localService: true }, { name: 'Samantha', lang: 'en-US', localService: true }, { name: 'Thomas', lang: 'fr-FR', localService: true }, { name: 'Google US English', lang: 'en-US', localService: false }];
  assert.equal(V.pickDeviceVoice(list).name, 'Samantha');
  assert.equal(V.pickDeviceVoice([{ name: 'Thomas', lang: 'fr-FR' }]), null);
});
