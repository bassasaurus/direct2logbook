(function () {
  'use strict';
  var form = document.querySelector('form[data-session-token-url]');
  if (!form || !window.fetch) return;
  var busy = false;
  var button = form.querySelector('button[type="submit"]');
  var status = form.querySelector('[data-login-status]');
  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    if (busy) return;
    busy = true;
    button.disabled = true;
    status.hidden = true;
    var controller = new AbortController();
    var timeout = setTimeout(function () { controller.abort(); }, 15000);
    try {
      // A suspended mobile tab may hold a token from an expired/rotated session.
      var response = await fetch(form.dataset.sessionTokenUrl, {
        credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: controller.signal,
        headers: {'Accept': 'application/json'}
      });
      if (!response.ok) throw new Error('Token refresh failed');
      var data = await response.json();
      if (!/^[A-Za-z0-9]{64}$/.test(data.csrf_token || '')) throw new Error('Invalid token');
      form.querySelector('[name="csrfmiddlewaretoken"]').value = data.csrf_token;
      HTMLFormElement.prototype.submit.call(form);
    } catch (error) {
      busy = false;
      button.disabled = false;
      status.textContent = 'Unable to connect. Please try again.';
      status.hidden = false;
    } finally {
      clearTimeout(timeout);
    }
  });
  window.addEventListener('pageshow', function (event) {
    if (event.persisted) window.location.reload();
  });
}());
