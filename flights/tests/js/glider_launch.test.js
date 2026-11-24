const test = require('node:test');
const assert = require('node:assert/strict');
const {launchState} = require('../../../static/js/glider_launch.js');
test('all actual glider flights require launch method, including existing blank records', () => {
  for (const original of [{}, {existing: true, method: '', aircraft: '1'}]) {
    assert.equal(launchState({category: 'GL'}, false, original, '', '1').required, true);
  }
  assert.equal(launchState({category: 'GL'}, true, {}, '', '1').visible, false);
  assert.equal(launchState({category: 'A'}, false, {}, '', '1').required, false);
});
test('Self-launch is only offered for capable gliders', () => {
  assert.deepEqual(launchState({category: 'GL'}, false, {}, '', '1').choices.map(x => x[0]), ['AEROTOW', 'GROUND']);
  assert.deepEqual(launchState({category: 'GL', self_launch_capable: true}, false, {}, '', '1').choices.map(x => x[0]), ['AEROTOW', 'GROUND', 'SELF']);
});
