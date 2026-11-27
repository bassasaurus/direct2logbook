(function () {
  for (const row of document.querySelectorAll('[data-record-match]')) {
    const aircraft = row.querySelector('select[name^="aircraft_"]');
    const tail = row.querySelector('select[name^="tailnumber_"]');
    if (!aircraft || !tail) continue;
    function clearTail() {
      tail.value = '';
      if (window.jQuery) window.jQuery(tail).val(null).trigger('change');
      else tail.dispatchEvent(new Event('change', {bubbles: true}));
    }
    if (window.jQuery) window.jQuery(aircraft).on('change.csvRecordMatch', clearTail);
    else aircraft.addEventListener('change', clearTail);
  }
  const form = document.querySelector('.csv-record-fields');
  const button = form?.querySelector('[data-record-continue]');
  if (button) {
    function validate() {
      for (const group of form.querySelectorAll('[data-new-tail-rules]')) {
        const skip = group.querySelector('input[type="checkbox"]');
        for (const radio of group.querySelectorAll('input[type="radio"]')) radio.required = !skip?.checked;
      }
      button.disabled = !form.checkValidity();
    }
    if (window.jQuery) window.jQuery(form).on('change.csvRecordValidation input.csvRecordValidation', validate);
    else {form.addEventListener('change', validate); form.addEventListener('input', validate);}
    validate();
  }
})();
