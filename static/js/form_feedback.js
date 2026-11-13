(function () {
  'use strict';
  document.querySelectorAll('form[data-submit-feedback]').forEach(function (form) {
    var submitted = false;
    var controls = Array.from(form.querySelectorAll('button[type="submit"], input[type="submit"]'));
    var originals = controls.map(function (button) {
      return {button: button, html: button.innerHTML, value: button.value};
    });
    var status = document.createElement('div');
    status.className = 'form-save-feedback alert alert-primary shadow-sm';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    status.hidden = true;
    form.appendChild(status);

    function reset() {
      submitted = false;
      status.hidden = true;
      form.removeAttribute('aria-busy');
      originals.forEach(function (item) {
        item.button.removeAttribute('aria-disabled');
        item.button.innerHTML = item.html;
        item.button.value = item.value;
      });
    }
    function show(message) {
      status.textContent = message;
      status.hidden = false;
      form.setAttribute('aria-busy', 'true');
      controls.forEach(function (button) {
        // Keep successful submitter names/values in the native POST payload.
        button.setAttribute('aria-disabled', 'true');
        if (button.tagName === 'BUTTON') button.textContent = message;
      });
    }
    form.addEventListener('submit', function (event) {
      if (submitted) { event.preventDefault(); return; }
      queueMicrotask(function () {
        if (event.defaultPrevented) return;
        submitted = true;
        show('Saving changes…');
      });
    }, true);
    form.addEventListener('form-feedback', function (event) {
      if (event.detail) show(event.detail);
      else if (!submitted) reset();
    });
    window.addEventListener('pageshow', reset);
  });
}());
