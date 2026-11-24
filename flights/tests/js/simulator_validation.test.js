const test = require('node:test');
const assert = require('node:assert/strict');
const {simulatorEntryErrors} = require('../../../static/js/simulator_validation.js');

test('web validation advances through simulator prerequisites in order', () => {
  let values = {simulator: true, instrument_credit_eligible: true};
  for (const [field, update] of [
    ['device_type', {device_type: 'ATD'}], ['atd_type', {atd_type: 'AATD'}],
    ['device_id', {device_id: 'A42'}], ['dual', {dual: true}],
    ['duration', {duration: '2.0'}], ['simulated_instrument', {simulated_instrument: '1.5'}],
  ]) {
    assert.deepEqual(Object.keys(simulatorEntryErrors(values)), [field]);
    values = {...values, ...update};
  }
  assert.deepEqual(simulatorEntryErrors(values), {});
  assert.equal(values.dual, true);
});

test('practice does not require an instructor; instrument time cannot exceed the session', () => {
  const values = {simulator: true, device_type: 'FFS', device_id: 'F42', duration: '2.0'};
  assert.deepEqual(simulatorEntryErrors(values), {});
  assert.deepEqual(simulatorEntryErrors({...values, instrument_credit_eligible: true}), {dual: 'Dual required.'});
  assert.ok(simulatorEntryErrors({...values, simulated_instrument: '2.1'}).simulated_instrument);
  assert.deepEqual(simulatorEntryErrors({...values, simulator: false}), {});
});
