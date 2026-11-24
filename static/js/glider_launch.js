(function (root) {
  'use strict';
  const choices = [['AEROTOW', 'Aerotow'], ['GROUND', 'Ground Launch'], ['SELF', 'Self-launch']];
  function launchState(aircraft, simulator) {
    const visible = Boolean(aircraft && aircraft.category === 'GL' && !simulator);
    return { visible, required: visible,
      choices: choices.filter(choice => choice[0] !== 'SELF' || Boolean(aircraft && aircraft.self_launch_capable)) };
  }
  if (typeof module !== 'undefined' && module.exports) { module.exports = {launchState}; return; }
  const wrapper = root.document.getElementById('flight-launch-fields');
  if (!wrapper) return;
  const form = wrapper.closest('form');
  const aircraft = form.querySelector('[name="aircraft_type"]');
  const simulator = form.querySelector('[name="simulator"]');
  const launch = form.querySelector('[name="launch_method"]');
  const metadata = JSON.parse(root.document.getElementById('launch-aircraft-metadata').textContent);
  let refreshing = false;
  function update(rebuild) {
    if (refreshing) return;
    refreshing = true;
    try {
      const selected = metadata[String(aircraft.value)];
      const state = launchState(selected, simulator.checked);
      if (rebuild) {
        const previous = launch.value;
        launch.replaceChildren(new Option('Choose launch method', ''));
        state.choices.forEach(choice => launch.add(new Option(choice[1], choice[0])));
        launch.value = state.choices.some(choice => choice[0] === previous) ? previous : '';
      }
      wrapper.hidden = !state.visible;
      // Unknown metadata must not erase an existing value while Select2 is
      // delivering a newly created aircraft's selection metadata.
      if (simulator.checked || selected && !state.visible) launch.value = '';
      launch.disabled = !state.visible && Boolean(selected || simulator.checked);
      launch.required = launchState(selected, simulator.checked).required;
      launch.dispatchEvent(new Event('change', {bubbles: true}));
    } finally { refreshing = false; }
  }
  launch.addEventListener('change', () => update(false));
  simulator.addEventListener('change', () => update(true));
  aircraft.addEventListener('change', () => update(true));
  if (root.jQuery) {
    root.jQuery(aircraft).on('change.gliderLaunch', () => update(true));
    root.jQuery(aircraft).on('select2:select.gliderLaunch', event => {
      const data = event.params.data;
      if (data.aircraft_category) metadata[String(data.id)] = {category: data.aircraft_category, self_launch_capable: data.self_launch_capable};
      update(true);
    });
  }
  update(true);
}(typeof window === 'undefined' ? this : window));
