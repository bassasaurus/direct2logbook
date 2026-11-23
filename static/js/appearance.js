/* Apply before styles load so saved appearance does not flash on navigation. */
(function () {
  'use strict';
  var root = document.documentElement;
  var key = 'd2lb.web.appearance';
  var forced = root.getAttribute('data-appearance');
  var preference = null;
  var system = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  function valid(value) { return value === 'dark' || value === 'light'; }
  try { var saved = window.localStorage.getItem(key); if (valid(saved)) preference = saved; } catch (_) { /* Storage may be blocked. */ }
  function apply() {
    var mode = valid(forced) ? forced : preference || (system && system.matches ? 'dark' : 'light');
    root.setAttribute('data-bs-theme', mode);
    document.querySelectorAll('[data-appearance-toggle]').forEach(function (button) {
      button.setAttribute('aria-label', mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
      button.setAttribute('title', mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
      button.setAttribute('aria-pressed', String(mode === 'dark'));
    });
  }
  apply();
  document.addEventListener('DOMContentLoaded', function () {
    apply();
    document.querySelectorAll('[data-appearance-toggle]').forEach(function (button) {
      button.addEventListener('click', function () {
        preference = root.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
        try { window.localStorage.setItem(key, preference); } catch (_) { /* Toggle still works for this page. */ }
        apply();
      });
    });
  });
  if (system && system.addEventListener) system.addEventListener('change', function () { if (!preference) apply(); });
  window.addEventListener('storage', function (event) {
    if (event.key !== key && event.key !== null) return;
    preference = valid(event.newValue) ? event.newValue : null;
    apply();
  });
}());
