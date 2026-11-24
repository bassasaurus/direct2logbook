(function () {
  'use strict';
  const container = document.getElementById('aircraft-default-controls');
  if (!container) return;
  const boxes = Array.from(container.querySelectorAll('[data-default-aircraft-code]'));
  const csrf = document.querySelector('#aircraft-default-settings input[name="csrfmiddlewaretoken"]').value;
  const status = document.getElementById('aircraft-default-status');
  let current = (boxes.find(box => box.checked) || {}).dataset;
  let selected = current ? current.defaultAircraftCode : '';
  let saving = false;
  let timer;
  function show(message, error) {
    clearTimeout(timer);
    status.textContent = message;
    status.hidden = !message;
    status.classList.toggle('text-danger', Boolean(error));
    if (message && !error) timer = setTimeout(() => { status.hidden = true; }, 3000);
  }
  function apply(code) { boxes.forEach(box => { box.checked = box.dataset.defaultAircraftCode === code; }); }
  boxes.forEach(function (box) {
    box.disabled = false;
    box.addEventListener('change', async function () {
      if (saving) { apply(selected); return; }
      saving = true;
      const code = box.checked ? box.dataset.defaultAircraftCode : '';
      apply(code);
      boxes.forEach(item => { item.disabled = true; });
      show('Saving…', false);
      try {
        const response = await fetch(container.dataset.url, {
          method: 'POST', credentials: 'same-origin',
          headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
          body: JSON.stringify({operation_id: crypto.randomUUID(), action: 'update',
            base_revision: container.dataset.revision, data: {aircraft_type: code}}),
        });
        if (!response.ok) {
          const latest = await fetch(container.dataset.url, {credentials: 'same-origin', cache: 'no-store'});
          if (latest.ok) {
            const record = await latest.json();
            selected = record.aircraft_type;
            container.dataset.revision = record.revision;
          }
          throw new Error(response.status === 409 ? 'Default changed. Try again.' : 'Default not saved. Try again.');
        }
        const result = await response.json();
        selected = result.record.aircraft_type;
        container.dataset.revision = result.record.revision;
        show('Default updated.', false);
      } catch (error) {
        show(error.message === 'Default changed. Try again.' ? error.message : 'Default not saved. Try again.', true);
      } finally {
        apply(selected);
        boxes.forEach(item => { item.disabled = false; });
        saving = false;
      }
    });
  });
}());
