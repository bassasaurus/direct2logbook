(function () {
  'use strict';
  var input = document.getElementById('route');
  var feedback = document.getElementById('route-airport-feedback');
  var hidden = document.getElementById('id_airport_choices');
  if (!input || !feedback || !hidden) return;
  var timer, controller, revision = 0, checkedRoute = null;
  var choices;
  try { choices = JSON.parse(hidden.value || '{}'); } catch (error) { choices = {}; }
  function routeValue() { return input.value.trim().replace(/\s+/g, '-').toUpperCase(); }
  function airportLabel(airport) {
    return airport.label || [airport.name, airport.city, airport.country, airport.icao].filter(Boolean).join(' — ');
  }
  function saveChoices(route) {
    choices.route = route;
    choices.airports = choices.airports || {};
    hidden.value = JSON.stringify(choices);
  }
  async function check(final) {
    var route = routeValue();
    if (final && checkedRoute === route) { input.value = route; return true; }
    checkedRoute = null;
    input.setCustomValidity('');
    input.classList.remove('is-invalid');
    input.removeAttribute('aria-invalid');
    if (final) input.value = route;
    feedback.classList.remove('text-muted');
    var current = ++revision;
    if (controller) controller.abort();
    feedback.replaceChildren();
    if (choices.route !== route) choices = {route: route, airports: {}};
    saveChoices(route);
    if (!route) return;
    controller = new AbortController();
    try {
      var response = await fetch(feedback.dataset.checkUrl + '?route=' + encodeURIComponent(route), {
        credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
        headers: {'Accept': 'application/json'}
      });
      if (current !== revision || route !== routeValue()) return;
      if (response.redirected || !response.ok) throw new Error('Unavailable');
      var data = await response.json();
      if (current !== revision || route !== routeValue()) return;
      var invalidCodes = [];
      data.entries.forEach(function (entry, index) {
        var line = document.createElement('div');
        line.className = 'small mb-1';
        if (entry.status === 'recognized') {
          line.classList.add('text-success');
          line.textContent = entry.code + ' — ' + airportLabel(entry.airport);
        } else if (entry.status === 'ambiguous') {
          var label = document.createElement('label');
          label.htmlFor = 'route-airport-choice-' + entry.position;
          label.className = 'text-warning mb-1';
          label.textContent = entry.code + ' — Which airport did you mean?';
          var select = document.createElement('select');
          select.id = label.htmlFor;
          select.className = 'form-control form-control-sm';
          select.add(new Option('Choose an airport', ''));
          entry.candidates.forEach(function (airport) { select.add(new Option(airportLabel(airport), String(airport.id))); });
          select.value = String(choices.airports[entry.position] || '');
          select.addEventListener('change', function () {
            if (select.value) choices.airports[entry.position] = Number(select.value);
            else delete choices.airports[entry.position];
            saveChoices(route);
            label.className = (select.value ? 'text-success' : 'text-warning') + ' mb-1';
            label.textContent = entry.code + (select.value ? ' — Airport selected' : ' — Which airport did you mean?');
          });
          line.append(label, select);
        } else {
          var typingLast = !final && index === data.entries.length - 1 && !/[^A-Za-z0-9]$/.test(input.value) && entry.code.length < 4;
          if (!typingLast) invalidCodes.push(entry.code);
          line.classList.add(typingLast ? 'text-muted' : 'text-danger');
          line.textContent = entry.code + (typingLast ? ' — Finish entering this airport code.' : ' — Airport not found.');
        }
        feedback.appendChild(line);
      });
      input.classList.toggle('is-invalid', invalidCodes.length > 0);
      if (invalidCodes.length) input.setAttribute('aria-invalid', 'true');
      else input.removeAttribute('aria-invalid');
      input.setCustomValidity(invalidCodes.length ? 'Unknown airport codes: ' + invalidCodes.join(', ') + '. Correct the route before saving.' : '');
      if (final && invalidCodes.length === 0) checkedRoute = route;
      return invalidCodes.length === 0;
    } catch (error) {
      if (error.name === 'AbortError' || current !== revision || route !== routeValue()) return;
      feedback.textContent = 'Airport check is unavailable. Your route will still be checked when saved.';
      feedback.classList.add('text-muted');
      return null;
    }
  }
  input.addEventListener('input', function () {
    checkedRoute = null;
    input.setCustomValidity('');
    input.classList.remove('is-invalid');
    input.removeAttribute('aria-invalid');
    clearTimeout(timer);
    revision += 1;
    if (controller) controller.abort();
    feedback.replaceChildren();
    if (choices.route !== routeValue()) { choices = {route: routeValue(), airports: {}}; saveChoices(routeValue()); }
    timer = window.setTimeout(function () { check(false); }, 450);
  });
  input.addEventListener('blur', function () { clearTimeout(timer); check(true); });
  var approvedRoute = null;
  var submitting = false;
  input.form.addEventListener('submit', async function (event) {
    if (event.defaultPrevented) return;
    if (approvedRoute === routeValue() || checkedRoute === routeValue()) {
      input.value = routeValue(); approvedRoute = null; return;
    }
    event.preventDefault();
    if (submitting) return;
    submitting = true;
    clearTimeout(timer);
    var route = routeValue();
    var submitter = event.submitter;
    var handedOff = false;
    input.form.dispatchEvent(new CustomEvent('form-feedback', {detail: 'Checking route…'}));
    try {
      var valid = await check(true);
      if (route !== routeValue() || valid === undefined) return;
      if (valid === false) {
        input.focus();
        input.reportValidity();
      } else {
        approvedRoute = route;
        input.form.requestSubmit(submitter || undefined);
        handedOff = true;
      }
    } finally {
      submitting = false;
      if (!handedOff) input.form.dispatchEvent(new CustomEvent('form-feedback', {detail: null}));
    }
  });
  if (input.value.trim()) check(true);
}());
