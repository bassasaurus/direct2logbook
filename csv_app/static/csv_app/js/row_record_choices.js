(function () {
  const options = JSON.parse(document.getElementById('csv-row-tailnumber-options')?.textContent || '{}');
  function showCustom(select) {
    const extra = select.parentElement.querySelector('[data-custom-record-field]');
    if (extra) extra.hidden = select.value !== '__custom__';
  }
  for (const select of document.querySelectorAll('[data-row-aircraft], [data-row-tailnumber]')) {
    showCustom(select);
    select.addEventListener('change', () => showCustom(select));
  }
  for (const aircraft of document.querySelectorAll('[data-row-aircraft]')) {
    const tail = document.querySelector('[data-row-tailnumber="' + aircraft.dataset.rowAircraft + '"]');
    if (!tail) continue;
    function updateTail() {
      const current = tail.value;
      const custom = aircraft.parentElement.querySelector('[data-custom-record-field] input');
      const designator = aircraft.value === '__custom__' ? custom?.value || '' : aircraft.value;
      const values = options[designator.toLowerCase()] || [];
      tail.replaceChildren(new Option('Choose tailnumber from file', ''));
      for (const value of values) tail.add(new Option(value, value));
      tail.add(new Option('Enter another…', '__custom__'));
      tail.value = values.includes(current) ? current : '';
      showCustom(tail);
    }
    aircraft.addEventListener('change', updateTail);
    aircraft.parentElement.querySelector('[data-custom-record-field] input')?.addEventListener('change', updateTail);
  }
})();
