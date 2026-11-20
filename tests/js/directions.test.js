'use strict';
// Every string the JavaScript port writes must equal what Python's routing.route() wrote.
const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../../src/atlas/web/routing.js');
const D = require('../../src/atlas/web/directions.js');
const { loadGolden, loadJson, SKIP } = require('./helpers.js');

const opts = { skip: SKIP };
const golden = loadGolden();
let G = null;
const graph = () => (G ||= core.loadGraph(loadJson()));

for (const pair of golden.pairs) {
  for (const profile of ['wheelchair', 'blind']) {
    test(`${pair.label} [${profile}]`, opts, () => {
      const want = pair.results[profile];
      const got = D.route(graph(), pair.from[0], pair.from[1], pair.to[0], pair.to[1], profile);
      if (want.reason === 'too_far') return assert.equal(got.error, 'too_far');
      if (want.reason === 'no_step_free_route') return assert.equal(got.error, 'no_route');
      const w = want.result;
      assert.equal(got.error, undefined);
      assert.deepEqual(got.directions, w.directions);
      assert.equal(got.length_feet, w.length_feet);
      assert.equal(got.compared_with_shortest, w.compared_with_shortest);
      assert.equal(got.crossings_text, w.crossings_text);
      assert.deepEqual(got.crossings, w.crossings);
      assert.equal(got.steep_sections, w.steep_sections);
      assert.equal(got.steps, w.steps);
      assert.equal(got.raised_kerbs, w.raised_kerbs);
      assert.equal(got.road_without_sidewalk_feet, w.road_without_sidewalk_feet);
      assert.deepEqual(got.shortest, w.shortest);
      assert.deepEqual(got.snap_feet, w.snap_feet);
      assert.equal(got.profile, w.profile);
    });
  }
}

test('Python rounding: halves go to the even number', () => {
  assert.equal(D.pyRound(0.5), 0);
  assert.equal(D.pyRound(1.5), 2);
  assert.equal(D.pyRound(2.5), 2);
  assert.equal(D.feet(3.048), '10 feet'); // 10 ft
  assert.equal(D.feet(0.5), '10 feet'); // never under 10
  assert.equal(D.feet(1609.344), '1.0 miles');
});

test('turn words and compass', () => {
  assert.equal(D.turn(0, 10), 'continue');
  assert.equal(D.turn(0, 45), 'bear right');
  assert.equal(D.turn(0, 315), 'bear left');
  assert.equal(D.turn(0, 90), 'turn right');
  assert.equal(D.turn(90, 0), 'turn left');
  assert.equal(D.turn(0, 180), 'turn around');
  assert.equal(D.bearing([0, 0], [0, 1]), 0);
  assert.equal(Math.round(D.bearing([0, 0], [1, 0])), 90);
});

test('crossing words and sentence', () => {
  assert.deepEqual(D.crossingWords({ signals: true, audible: true, tactile: true }), [
    'Cross at the traffic signal',
    'audible signal; tactile paving at the curb',
  ]);
  assert.deepEqual(D.crossingWords({ kind: 'unmarked' }), ['Cross at an unmarked crossing', 'no signal']);
  assert.deepEqual(D.crossingWords({}), ['Cross the street', 'crossing type not mapped']);
  assert.equal(D.crossingSentence({ total: 0 }), 'No street crossings.');
  assert.equal(
    D.crossingSentence({ total: 3, signals: 1, audible: 0, marked: 1, unmarked_or_unknown: 1 }),
    '3 street crossings: 1 with traffic signals (0 audible), 1 marked without a signal, 1 unmarked or not mapped.'
  );
});

test('every golden step list is non-empty except the same-point case', { skip: SKIP }, () => {
  for (const pair of golden.pairs) {
    const r = pair.results.wheelchair.result;
    if (r && pair.category !== 'same point') assert.ok(r.directions.length > 0);
  }
});
