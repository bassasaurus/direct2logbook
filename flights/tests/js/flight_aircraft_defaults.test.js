const test = require('node:test');
const assert = require('node:assert/strict');
const {flightDefaults} = require('../../../static/js/flight_aircraft_defaults.js');
test('aircraft roles remain exclusive and XC is independent', () => {
  assert.deepEqual(flightDefaults({default_crew_role:'PIC',default_cross_country:true},false),
    {pilot_in_command:true,second_in_command:false,cross_country:true});
  assert.deepEqual(flightDefaults({default_crew_role:'SIC'},false),
    {pilot_in_command:false,second_in_command:true,cross_country:false});
  assert.deepEqual(flightDefaults({},false),
    {pilot_in_command:false,second_in_command:false,cross_country:false});
});
test('XC is never prefilled for simulator sessions', () => {
  assert.equal(flightDefaults({default_crew_role:'PIC',default_cross_country:true},true).cross_country,false);
});
