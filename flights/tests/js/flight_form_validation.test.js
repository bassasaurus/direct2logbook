const test = require('node:test');
const assert = require('node:assert/strict');
const {flightEntryErrors} = require('../../../static/js/flight_form_validation.js');
const {simulatorEntryErrors} = require('../../../static/js/simulator_validation.js');
const valid = {date: 'Nov 23, 2026', aircraft_type: '737', registration: 'N737', route: 'IAH-ORD', duration: '2.5', pilot_in_command: true};

test('night cannot exceed duration and editing duration rechecks the limit', () => {
  for (const night of ['', '0', '0.3', '2.5']) assert.equal(flightEntryErrors({...valid, night}, simulatorEntryErrors).night, undefined);
  assert.equal(flightEntryErrors({...valid, night: '2.6'}, simulatorEntryErrors).night, 'Night cannot exceed Duration.');
  assert.equal(flightEntryErrors({...valid, night: '1.2', duration: '1.1'}, simulatorEntryErrors).night, 'Night cannot exceed Duration.');
  assert.equal(flightEntryErrors({...valid, night: '1.2', duration: '1.2'}, simulatorEntryErrors).night, undefined);
  assert.equal(flightEntryErrors({...valid, night: '1.2', duration: ''}, simulatorEntryErrors).night, undefined);
});

test('required fields are identified immediately, and valid ordinary entries clear them', () => {
  assert.deepEqual(flightEntryErrors({}, simulatorEntryErrors), {date: 'Required', aircraft_type: 'Required', duration: 'Required', registration: 'Required', route: 'Required', flight_role: 'Required'});
  assert.deepEqual(flightEntryErrors(valid, simulatorEntryErrors), {});
});

test('sim entries replace tail and route requirements with staged device feedback', () => {
  let values = {...valid, simulator: true, registration: '', route: ''};
  assert.deepEqual(flightEntryErrors(values, simulatorEntryErrors), {device_type: 'Select device type.'});
  values = {...values, device_type: 'ATD', device_id: 'A42', instrument_credit_eligible: true};
  assert.deepEqual(flightEntryErrors(values, simulatorEntryErrors), {atd_type: 'Select BATD or AATD.'});
  values.atd_type = 'AATD';
  assert.deepEqual(flightEntryErrors(values, simulatorEntryErrors), {dual: 'Dual required.'});
  values.dual = true;
  assert.deepEqual(flightEntryErrors(values, simulatorEntryErrors), {simulated_instrument: 'Instrument time required.'});
  values.simulated_instrument = '1.5';
  assert.deepEqual(flightEntryErrors(values, simulatorEntryErrors), {});
});

test('solo landings and positive duration receive inline feedback', () => {
  assert.equal(flightEntryErrors({...valid, duration: '0'}, simulatorEntryErrors).duration, 'Must be greater than 0.');
  assert.ok(flightEntryErrors({...valid, solo: true}, simulatorEntryErrors).landings_day);
  assert.deepEqual(flightEntryErrors({...valid, solo: true, landings_night: 1}, simulatorEntryErrors), {});
});


test('Full Stop requires Night landings and Night duration', () => {
  const selected = {...valid,night_landings_full_stop:true};
  assert.equal(flightEntryErrors(selected, simulatorEntryErrors).night_landings_full_stop,'Enter Night landings.');
  assert.equal(flightEntryErrors({...selected,landings_night:1}, simulatorEntryErrors).night,'Night time required for Full Stop.');
  assert.deepEqual(flightEntryErrors({...selected,landings_night:1,night:'.1'}, simulatorEntryErrors),{});
});


test('commas and tabs anywhere in Remarks block submission until corrected', () => {
  for (const remarks of [',note','note,','one,two'])
    assert.equal(flightEntryErrors({...valid,remarks},simulatorEntryErrors).remarks,'Remove commas to prevent export corruption.');
  for (const remarks of ['\tnote','note\t','one\ttwo'])
    assert.equal(flightEntryErrors({...valid,remarks},simulatorEntryErrors).remarks,'Remove tabs to prevent export corruption.');
  assert.equal(flightEntryErrors({...valid,remarks:'one, two\tthree'},simulatorEntryErrors).remarks,'Remove commas to prevent export corruption. Remove tabs to prevent export corruption.');
  assert.deepEqual(flightEntryErrors({...valid,remarks:'Corrected notes'},simulatorEntryErrors),{});
});
