/* Check the same Django form used by Continue, without saving the batch. */
(function () {
  const form = document.getElementById('csv-mapping-form');
  const button = form?.querySelector('[data-mapping-continue]');
  if (!button) return;
  const status = form.querySelector('[data-mapping-validation]');
  let generation = 0, timer, controller;
  function schedule() {
    const current = ++generation;
    clearTimeout(timer);
    controller?.abort();
    button.disabled = true;
    status.textContent = 'Checking choices…';
    timer = setTimeout(async function () {
      controller = new AbortController();
      try {
        const body = new FormData(form);
        body.set('validate_only', '1');
        const response = await fetch(form.action, {method: 'POST', body, credentials: 'same-origin',
          signal: controller.signal, headers: {'Accept': 'application/json'}});
        if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Validation unavailable');
        const result = await response.json();
        if (current !== generation) return;
        button.disabled = result.valid !== true;
        for (const [name, required] of Object.entries(result.mapping_requirements || {})) {
          const select = form.elements.namedItem(name);
          if (select) {
            select.required = required;
            const label = select.closest('[data-mapping-row]')?.querySelector('[data-required-label]');
            if (label) label.hidden = !required;
          }
        }
        for (const field of form.elements) {
          if (!field.setCustomValidity || !field.name) continue;
          const errors = result.errors[field.name] || [];
          field.setCustomValidity(errors.map(error => error.message).join(' '));
          if (errors.length) field.setAttribute('aria-invalid', 'true');
          else field.removeAttribute('aria-invalid');
        }
        status.textContent = result.valid ? '' : Object.values(result.errors).flat().map(error => error.message).join(' ');
        const year = form.querySelector('[data-year-confirmation]');
        if (year) year.hidden = !result.year_required;
        const checks = result.block_checks || [];
        const comparison = form.querySelector('[data-live-block-checks]');
        const rows = form.querySelector('[data-block-check-rows]');
        if (comparison && rows) {
          comparison.hidden = !checks.length;
          rows.replaceChildren();
          for (const check of checks.slice(0, 20)) {
            const row = document.createElement('tr');
            for (const value of [check.line, check.out, check.arrival, check.selected ?? '—', check.calculated ?? '—',
              check.error || (check.difference ? 'Duration differs' : check.from_blocks ? 'Calculated' : 'Matches')]) {
              const cell = document.createElement('td'); cell.textContent = String(value); row.appendChild(cell);
            }
            rows.appendChild(row);
          }
          const count = form.querySelector('[data-block-check-count]');
          if (count) {count.hidden = !checks.length; count.textContent = `Showing ${Math.min(20, checks.length)} of ${checks.length} block-time checks.`;}
        }
      } catch (error) {
        if (current !== generation || error.name === 'AbortError') return;
        status.textContent = 'Unable to check choices. Check your connection or reload the preview.';
      }
    }, 200);
  }
  form.addEventListener('input', schedule);
  form.addEventListener('change', schedule);
  form.addEventListener('submit', function (event) {if (button.disabled) event.preventDefault();});
  window.addEventListener('pageshow', schedule);
  schedule();
})();
