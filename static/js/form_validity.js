(function (root) {
  'use strict';
  // Review/navigation actions must remain usable to correct server-validated data.
  const managedElsewhere = '[formnovalidate], [data-validation-request], [data-mapping-continue], [data-record-continue], #csv-inspect-submit';
  function active(field) { return !field.disabled && !field.closest('[hidden]'); }
  function formIsValid(form) {
    if (form.dataset.aircraftValid === 'false' || form.dataset.signatureValid === 'false') return false;
    if (Array.from(form.elements).some(field => active(field) && field.willValidate && !field.validity.valid)) return false;
    if (Array.from(form.querySelectorAll('input.is-invalid, select.is-invalid, textarea.is-invalid, input[aria-invalid="true"], select[aria-invalid="true"], textarea[aria-invalid="true"], .required-choice-empty')).some(active)) return false;
    const password = form.elements.namedItem('password1');
    const confirmation = form.elements.namedItem('password2');
    return !(password && confirmation && active(confirmation) && password.value !== confirmation.value);
  }
  function setupForm(form) {
    function buttons() {
      return Array.from(form.querySelectorAll('button:not([type]), button[type="submit"], input[type="submit"]'))
        .filter(button => !button.matches(managedElsewhere));
    }
    function update() {
      const disabled = !formIsValid(form);
      buttons().forEach(button => { if (button.disabled !== disabled) button.disabled = disabled; });
    }
    const schedule = () => root.queueMicrotask(update);
    form.addEventListener('input', schedule);
    form.addEventListener('change', schedule);
    form.addEventListener('form-validation', update);
    if (root.jQuery) root.jQuery(form).on('input.submitValidity change.submitValidity changeDate.submitValidity', schedule);
    form.addEventListener('submit', function (event) {
      const controls = buttons();
      if (!controls.length || event.submitter && !controls.includes(event.submitter)) return;
      if (!formIsValid(form)) { event.preventDefault(); update(); }
    }, true);
    root.addEventListener('pageshow', schedule);
    // Handles conditional requirements and asynchronous validators (e.g. airports).
    if (root.MutationObserver) new root.MutationObserver(records => {
      if (records.some(record => !record.target.matches('button, input[type="submit"]'))) schedule();
    }).observe(form, {subtree:true,childList:true,attributes:true,
      attributeFilter:['required','disabled','hidden','class','aria-invalid','data-aircraft-valid','data-signature-valid']});
    update();
    return update;
  }
  if (typeof module !== 'undefined' && module.exports) { module.exports = {formIsValid, setupForm}; return; }
  const initialized = new WeakSet();
  function initialize(form) {
    if (!initialized.has(form)) { initialized.add(form); setupForm(form); }
  }
  root.document.querySelectorAll('form').forEach(initialize);
  new root.MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node.nodeType !== 1) return;
    if (node.matches('form')) initialize(node);
    node.querySelectorAll('form').forEach(initialize);
  }))).observe(root.document.body, {childList:true,subtree:true});
}(typeof window === 'undefined' ? globalThis : window));
