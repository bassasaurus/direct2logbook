(function (root) {
  'use strict';
  function flightEntryErrors(values, simulatorErrors) {
    const errors = {};
    ['date', 'aircraft_type', 'duration'].forEach(function (name) {
      if (!String(values[name] == null ? '' : values[name]).trim()) errors[name] = 'Required';
    });
    if (!values.simulator) {
      ['registration', 'route'].forEach(function (name) {
        if (!String(values[name] || '').trim()) errors[name] = 'Required';
      });
    } else Object.assign(errors, simulatorErrors(values));
    if (!['pilot_in_command', 'second_in_command', 'solo', 'dual'].some(function (name) { return values[name]; }))
      errors.flight_role = 'Required';
    if (values.solo && !(Number(values.landings_day) > 0 || Number(values.landings_night) > 0))
      errors.landings_day = 'Day or Night landings required.';
    if (String(values.duration || '').trim() && !(Number(values.duration) > 0)) errors.duration = 'Must be greater than 0.';
    return errors;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {flightEntryErrors};
    return;
  }
  root.document.querySelectorAll('form[data-flight-validation]').forEach(function (form) {
    const fields = Array.from(form.querySelectorAll('input[name], select[name], textarea[name]'))
      .filter(function (field) { return !['hidden', 'submit', 'button'].includes(field.type); });
    const feedback = new Map();
    const serverErrors = new Map();
    fields.forEach(function (field) {
      const original = root.document.getElementById('id_' + field.name + '_error');
      if (original) { serverErrors.set(field.name, original.textContent.trim()); original.remove(); }
      const message = root.document.createElement('div');
      message.id = field.id + '-feedback';
      message.className = 'invalid-feedback';
      message.hidden = true;
      const sibling = field.nextElementSibling;
      const anchor = sibling && (sibling.classList.contains('select2-container') || sibling.tagName === 'LABEL') ? sibling : field;
      anchor.insertAdjacentElement('afterend', message);
      const described = (field.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
      described.push(message.id);
      field.setAttribute('aria-describedby', described.join(' '));
      feedback.set(field, message);
    });
    const group = root.document.getElementById('flight-role-fields');
    const groupFeedback = root.document.createElement('div');
    groupFeedback.className = 'invalid-feedback';
    groupFeedback.id = 'flight-role-feedback';
    groupFeedback.hidden = true;
    group.insertAdjacentElement('afterend', groupFeedback);
    group.setAttribute('aria-describedby', groupFeedback.id);
    form.noValidate = true;

    function values() {
      const result = {};
      fields.forEach(function (field) { result[field.name] = field.type === 'checkbox' ? field.checked : field.value; });
      return result;
    }
    function update(event) {
      if (event && event.target && event.target.name) {
        serverErrors.delete(event.target.name);
        if (['simulator', 'device_type', 'atd_type'].includes(event.target.name))
          ['device_type', 'device_id', 'atd_type'].forEach(function (name) { serverErrors.delete(name); });
        if (event.target.name === 'aircraft_type' || event.target.name === 'instrument_credit_eligible')
          serverErrors.delete('instrument_credit_eligible');
        if (['pilot_in_command', 'second_in_command', 'solo', 'dual'].includes(event.target.name))
          serverErrors.delete('pilot_in_command');
      }
      const current = values();
      const errors = flightEntryErrors(current, root.simulatorEntryErrors);
      fields.forEach(function (field) {
        const message = feedback.get(field);
        const hidden = field.disabled || Boolean(field.closest('[hidden]'));
        let error = hidden ? '' : serverErrors.get(field.name) || errors[field.name] || '';
        if (!error && !hidden && field.validity && !field.validity.valid) {
          if (field.validity.valueMissing) error = 'Required';
          else if (field.validity.badInput) error = 'Numbers only';
          else if (field.validity.stepMismatch) error = field.step === '1' ? 'Whole numbers only' : 'Use tenths';
          else if (field.validity.customError && field.name === 'route') error = 'Check route airports.';
          else error = 'Check this value.';
        }
        field.setAttribute('aria-required', String(Boolean(field.required)));
        field.classList.toggle('is-invalid', Boolean(error));
        if (error) field.setAttribute('aria-invalid', 'true');
        else field.removeAttribute('aria-invalid');
        message.textContent = error === 'Required' ? '' : error;
        message.hidden = !error || error === 'Required';
        message.classList.toggle('d-block', Boolean(error) && error !== 'Required');
      });
      group.classList.toggle('flight-role-invalid', Boolean(errors.flight_role));
      groupFeedback.textContent = '';
      groupFeedback.hidden = true;
      groupFeedback.classList.remove('d-block');
      return fields.find(function (field) { return field.classList.contains('is-invalid'); }) || (errors.flight_role ? group : null);
    }
    if (root.jQuery) root.jQuery(form).on('input.flightValidation change.flightValidation changeDate.flightValidation', update);
    else { form.addEventListener('input', update); form.addEventListener('change', update); }
    form.addEventListener('submit', function (event) {
      const invalid = update();
      if (!invalid) return;
      event.preventDefault();
      const select2 = invalid.tagName === 'SELECT' && invalid.parentElement.querySelector('.select2-selection');
      (select2 || invalid).focus();
    }, true);
    root.addEventListener('pageshow', function () { update(); });
    update();
  });
}(typeof window === 'undefined' ? this : window));
