(function () {
  'use strict';
  document.querySelectorAll('form[data-submit-feedback]').forEach(function (form) {
    var submitted = false;
    var savingMessage = form.dataset.submitFeedback === 'delete' ? 'Deleting…'
      : form.dataset.submitFeedback === 'create' ? 'Saving…' : 'Saving changes…';
    var controls = Array.from(form.querySelectorAll('button[type="submit"], input[type="submit"]'));
    var originals = controls.map(function (button) {
      return {button: button, html: button.innerHTML, value: button.value};
    });
    var status = document.createElement('div');
    status.className = 'visually-hidden';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    status.hidden = true;
    document.body.appendChild(status);
    var lockedNodes = [];

    function lockPage() {
      if (!lockedNodes.length) {
        lockedNodes = Array.from(document.body.children).filter(function (node) {
          return node !== status && !['SCRIPT', 'STYLE', 'LINK'].includes(node.tagName);
        }).map(function (node) {
          var previous = {node: node, inert: node.inert};
          node.inert = true;
          return previous;
        });
      }
      document.body.classList.add('is-saving');
    }

    function reset() {
      submitted = false;
      status.hidden = true;
      status.textContent = '';
      document.body.classList.remove('is-saving');
      lockedNodes.forEach(function (item) { item.node.inert = item.inert; });
      lockedNodes = [];
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
      lockPage();
      controls.forEach(function (button) {
        // Keep successful submitter names/values in the native POST payload.
        button.setAttribute('aria-disabled', 'true');
        if (button.tagName === 'BUTTON') button.textContent = message;
      });
    }
    form.addEventListener('submit', function (event) {
      if (submitted) { event.preventDefault(); return; }
      // Browsers can run microtasks between submit listeners, before an inline
      // confirmation cancels the event. Wait for the entire dispatch to finish.
      setTimeout(function () {
        if (event.defaultPrevented) return;
        submitted = true;
        show(savingMessage);
      });
    }, true);
    form.addEventListener('form-feedback', function (event) {
      if (event.detail) show(event.detail);
      else if (!submitted) reset();
    });
    window.addEventListener('pageshow', reset);
  });
}());
