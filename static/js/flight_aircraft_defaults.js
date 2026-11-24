(function (root) {
  'use strict';
  function flightDefaults(aircraft, simulator) {
    return {pilot_in_command: aircraft.default_crew_role === 'PIC',
      second_in_command: aircraft.default_crew_role === 'SIC',
      cross_country: !simulator && aircraft.default_cross_country === true};
  }
  if (typeof module !== 'undefined' && module.exports) { module.exports = {flightDefaults}; return; }
  const data = root.document.getElementById('flight-aircraft-defaults-data');
  if (!data) return; // Existing flights keep their recorded values.
  const defaults = JSON.parse(data.textContent);
  const aircraft = root.document.getElementById('id_aircraft_type');
  let current = aircraft.value;
  function update(event) {
    const choice = event.params && event.params.data;
    let refreshed = false;
    if (choice) {
      const previous = defaults[String(choice.id)];
      refreshed = !previous || previous.default_crew_role !== choice.default_crew_role
        || previous.default_cross_country !== choice.default_cross_country;
      defaults[String(choice.id)] = choice;
    }
    if (!aircraft.value) { current = ''; return; }
    if ((aircraft.value === current && !refreshed) || !defaults[aircraft.value]) return;
    current = aircraft.value;
    const values = flightDefaults(defaults[current], root.document.getElementById('id_simulator').checked);
    root.document.getElementById('pic').checked = values.pilot_in_command;
    root.document.getElementById('sic').checked = values.second_in_command;
    const selected = values.pilot_in_command ? 'pic' : values.second_in_command ? 'sic' : null;
    // Reuse the form's existing role-exclusion and simulator rules.
    if (selected) root.jQuery('#' + selected).trigger('change');
    root.document.getElementById('id_cross_country').checked = values.cross_country;
    root.jQuery('#id_cross_country').trigger('change');
  }
  root.jQuery(aircraft).on('change.aircraftDefaults select2:select.aircraftDefaults', update);
}(typeof window === 'undefined' ? this : window));
