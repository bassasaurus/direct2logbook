(function () {
  'use strict';
  var element = document.getElementById('confirm-removal');
  if (!element) return;
  var pending = null, approved = null, confirmed = false;
  var confirmButton = document.getElementById('confirm-removal-submit');
  document.addEventListener('submit', function (event) {
    var button = event.submitter;
    if (!button || !button.hasAttribute('data-confirm-removal')) return;
    if (approved === button) { approved = null; return; }
    event.preventDefault();
    if (!window.bootstrap || !window.bootstrap.Modal || pending) return;
    pending = { form: event.target, button: button };
    confirmed = false;
    confirmButton.disabled = false;
    document.getElementById('confirm-removal-title').textContent = button.dataset.confirmTitle;
    document.getElementById('confirm-removal-message').textContent = button.dataset.confirmMessage;
    var selected = event.target.querySelector('input[name="email"]:checked');
    document.getElementById('confirm-removal-detail').textContent = selected ? selected.value : button.dataset.confirmDetail || '';
    window.bootstrap.Modal.getOrCreateInstance(element).show();
  });
  confirmButton.addEventListener('click', function () {
    if (!pending || confirmed) return;
    confirmed = true;
    confirmButton.disabled = true;
    window.bootstrap.Modal.getOrCreateInstance(element).hide();
  });
  element.addEventListener('hidden.bs.modal', function () {
    var action = pending;
    pending = null;
    if (!action) return;
    action.button.focus();
    if (confirmed && action.form.isConnected && action.button.isConnected) {
      approved = action.button;
      // Preserve the original submitter (including allauth's action_remove).
      action.form.requestSubmit(action.button);
      approved = null;
    }
    confirmed = false;
  });
}());
