(function () {
  'use strict';
  var forms = Array.from(document.querySelectorAll('form[data-unsaved-changes]'));
  if (!forms.length) return;

  function snapshot(form) {
    var values = [];
    new FormData(form).forEach(function (value, name) {
      if (name === 'csrfmiddlewaretoken') return;
      if (value instanceof File) {
        values.push([name, value.name, value.size, value.name ? value.lastModified : 0]);
      } else {
        values.push([name, value]);
      }
    });
    return JSON.stringify(values);
  }
  var states = forms.map(function (form) {
    return {form: form, initial: snapshot(form), submitting: false};
  });
  function dirty() {
    return states.some(function (state) {
      return !state.submitting && snapshot(state.form) !== state.initial;
    });
  }
  function warn(event) {
    if (!dirty()) return;
    event.preventDefault();
    event.returnValue = '';
  }
  function update() {
    window.removeEventListener('beforeunload', warn);
    if (dirty()) window.addEventListener('beforeunload', warn);
  }
  states.forEach(function (state) {
    state.form.addEventListener('input', update);
    state.form.addEventListener('change', update);
    // Select2 sends jQuery change events rather than native DOM change events.
    if (window.jQuery) window.jQuery(state.form).on('change', update);
    state.form.addEventListener('submit', function (event) {
      // Observe validation handlers that cancel submission before suppressing warnings.
      queueMicrotask(function () {
        state.submitting = !event.defaultPrevented;
        update();
      });
    });
    state.form.addEventListener('reset', function () { setTimeout(update, 0); });
  });
  window.addEventListener('pageshow', function () {
    states.forEach(function (state) { state.submitting = false; });
    update();
  });
}());
