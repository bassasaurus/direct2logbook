(function () {
  'use strict';
  const form = document.getElementById('aircraft-flight-defaults');
  if (!form) return;
  let saved = JSON.parse(document.getElementById('aircraft-flight-defaults-data').textContent);
  const roles = Array.from(form.querySelectorAll('[data-crew-role]'));
  const xc = form.querySelector('#default-xc');
  const boxes = [...roles, xc];
  const status = form.querySelector('[role="status"]');
  let busy = false, timer;
  const apply = () => {
    roles.forEach(box => { box.checked = box.dataset.crewRole === saved.default_crew_role; });
    xc.checked = saved.default_cross_country;
  };
  function show(message, error) {
    clearTimeout(timer);
    status.textContent = message;
    status.hidden = !message;
    status.classList.toggle('text-danger', error);
    if (!error) timer = setTimeout(() => { status.hidden = true; }, 3000);
  }
  form.addEventListener('submit', event => event.preventDefault());
  boxes.forEach(box => box.addEventListener('change', async () => {
    if (busy) { apply(); return; }
    if (box.dataset.crewRole && box.checked) roles.forEach(other => { if (other !== box) other.checked = false; });
    busy = true;
    boxes.forEach(input => { input.disabled = true; });
    show('Saving…', false);
    try {
      const response = await fetch(form.dataset.url, {method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value},
        body: JSON.stringify({base_revision: saved.revision,
          default_crew_role: roles.find(input => input.checked)?.dataset.crewRole || '', default_cross_country: xc.checked})});
      const result = await response.json();
      if (result.record) saved = result.record;
      if (!response.ok) throw new Error(response.status === 409 ? 'Defaults changed. Review and try again.' : 'Defaults not saved. Try again.');
      show('Defaults saved.', false);
    } catch (error) {
      show(error.message === 'Defaults changed. Review and try again.' ? error.message : 'Defaults not saved. Try again.', true);
    } finally {
      apply(); busy = false;
      boxes.forEach(input => { input.disabled = false; });
    }
  }));
}());
