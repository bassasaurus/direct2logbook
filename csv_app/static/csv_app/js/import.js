(function () {
  const form = document.getElementById('csv-preview-form');
  const input = form?.querySelector('input[type="file"]');
  if (!input) return;
  const button = form.querySelector('#csv-inspect-submit');
  const label = button.querySelector('[data-review-label]');
  const spinner = button.querySelector('[data-review-spinner]');
  const progress = form.querySelector('[data-review-progress]');
  const zone = form.querySelector('[data-file-drop]');
  const maxBytes = Number(zone?.dataset?.maxBytes) || 20 * 1024 * 1024;
  const fileStatus = zone?.querySelector('[data-file-drop-status]');
  function missingOrOversized() {
    const tooLarge = input.files?.[0]?.size > maxBytes;
    if (fileStatus) fileStatus.textContent = tooLarge ? 'Choose a file no larger than ' + maxBytes / (1024 * 1024) + ' MB.' : '';
    return !input.files?.length || tooLarge;
  }
  let reviewing = false;
  function reset() {
    reviewing = false;
    button.disabled = missingOrOversized();
    button.removeAttribute('aria-busy');
    label.textContent = 'Review file';
    spinner.classList.add('d-none');
    progress.hidden = true;
  }
  input.addEventListener('change', function () {
    if (!reviewing) button.disabled = missingOrOversized();
  });
  form.addEventListener('submit', function (event) {
    if (reviewing || missingOrOversized()) { event.preventDefault(); return; }
    if (event.defaultPrevented) return;
    reviewing = true;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    label.textContent = 'Reviewing file…';
    spinner.classList.remove('d-none');
    progress.hidden = false;
  });
  window.addEventListener('pageshow', reset);
  reset();
})();

  (function () {
    var button = $('#csv_upload');
    var status = $('#csv-import-status');
    var another = $('#csv-choose-another');
    var pending = false;
    var timer;
    var generation = 0;

    function show(message, state) {
      var color = state === 'completed' ? 'text-success' : state === 'failed' || state === 'needs_review' ? 'text-danger' :
        state === 'unconfirmed' || state === 'expired' ? 'text-warning' : 'text-info';
      status.removeClass('d-none text-info text-success text-warning text-danger').addClass(color).text(message);
    }
    function setButton(state) {
      $('[data-csv-step]').removeAttr('aria-current');
      $('[data-csv-step="' + (state === 'needs_review' ? '5' : '8') + '"]').attr('aria-current', 'step');
      var labels = {submitting: 'Submitting…', queued: 'Queued', processing: 'Importing…',
        unconfirmed: 'Checking request…', completed: 'Imported', failed: 'Import failed', expired: 'Preview expired', needs_review: 'Correct aircraft/tailnumber'};
      var terminal = ['completed', 'failed', 'expired', 'needs_review'].indexOf(state) !== -1;
      var color = state === 'completed' ? 'btn-success' : state === 'failed' ? 'btn-outline-danger' :
        state === 'expired' ? 'btn-outline-secondary' : 'btn-primary';
      pending = true;
      button.removeClass('btn-primary btn-success btn-outline-danger btn-outline-secondary')
        .addClass(color).prop('disabled', true).text(labels[state] || 'Importing…');
      if (terminal) button.removeAttr('aria-busy');
      else button.attr('aria-busy', 'true');
      if (state === 'completed') $('#csv-view-logbook').removeClass('d-none');
    }
    function allowStatusCheck() {
      pending = false;
      button.removeAttr('aria-busy').prop('disabled', false).text('Check request');
    }
    function returnToRecords(data, navigate) {
      if (data.status !== 'needs_review' || !data.review_url) return false;
      clearTimeout(timer);
      generation++;
      show(data.message, data.status);
      if (navigate) {
        setButton(data.status);
        window.location.assign(data.review_url);
      } else {
        status.append(' ', $('<a>').attr('href', data.review_url).text(data.review_label || 'Correct aircraft/tailnumber'));
      }
      return true;
    }
    function track(url, lockButton) {
      if (!url) return;
      clearTimeout(timer);
      var current = ++generation;
      var started = Date.now();
      function check() {
        $.ajax({url: url, dataType: 'json', cache: false, timeout: 15000})
          .done(function (data) {
            if (current !== generation) return;
            if (returnToRecords(data, lockButton)) return;
            show(data.message, data.status);
            if (lockButton) setButton(data.status);
            if (data.status === 'completed' || data.status === 'failed' || data.status === 'expired') return;
            if (Date.now() - started < 1200000) timer = setTimeout(check, 2000);
            else {
              status.append(' Refresh this page to check again.');
              if (lockButton) allowStatusCheck();
            }
          }).fail(function () {
            if (current !== generation) return;
            show('Import status is temporarily unavailable. Check this request again before starting another import.', 'unconfirmed');
            if (lockButton) allowStatusCheck();
          });
      }
      check();
    }
    track(status.attr('data-status-url'), false);
    button.on('click', function () {
      if (pending) return;
      clearTimeout(timer);
      generation++;
      setButton('submitting');
      another.addClass('disabled').attr({'aria-disabled': 'true', tabindex: '-1'});
      show('Submitting your import request…', 'queued');
      $.ajax({
        type: 'POST', url: $('#csv-preview-form').attr('data-import-url'),
        data: {csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').val(), batch_id: $('#csv-batch-id').val()},
        dataType: 'json', timeout: 45000
      }).done(function (data) {
        if (returnToRecords(data, true)) return;
        show(data.message, data.status);
        setButton(data.status);
        if (data.status !== 'completed' && data.status !== 'failed') track(data.status_url, true);
      }).fail(function (xhr) {
        var data = xhr.responseJSON || {};
        if (returnToRecords(data, true)) return;
        var state = xhr.status === 410 ? 'expired' : data.status || 'unconfirmed';
        var message = data.message;
        if (xhr.status === 403) message = 'Your session could not be verified. Refresh and sign in again.';
        if (xhr.status === 404) message = 'This preview is no longer available. Choose another CSV.';
        show(message || 'Queue submission could not be confirmed. Check this same request safely.', state);
        if (data.review_url) status.append(' ', $('<a>').attr('href', data.review_url).text(data.review_label || 'Review possible matches'));
        if (data.status_url && data.status !== 'failed') {
          setButton(state);
          track(data.status_url, true);
        } else if (xhr.status === 410 || data.status === 'failed' || xhr.status === 400 || xhr.status === 403 || xhr.status === 404) {
          setButton(xhr.status === 410 ? 'expired' : 'failed');
        } else allowStatusCheck();
      }).always(function () {
        another.removeClass('disabled').removeAttr('aria-disabled tabindex');
      });
    });
  })();

(function () {
  const form = document.getElementById('csv-mapping-form');
  if (!form) return;
  const selects = Array.from(form.querySelectorAll('[data-column-map]'));
  const dependencies = JSON.parse(document.getElementById('csv-mapping-dependencies')?.textContent || '{}');
  const formats = JSON.parse(document.getElementById('csv-column-formats')?.textContent || '{}');
  const sampleRows = JSON.parse(document.getElementById('csv-sample-rows')?.textContent || '[]');
  const routeColumns = JSON.parse(document.getElementById('csv-route-columns')?.textContent || '[]');
  const hourFields = JSON.parse(document.getElementById('csv-hour-fields')?.textContent || '[]');
  const units = form.querySelector('[name="time_units"]');
  const nativeTimes = JSON.parse(document.getElementById('csv-native-times')?.textContent || 'false');
  const unused = form.querySelector('[data-unused-columns]');
  const sourceRows = Array.from(form.querySelectorAll('[data-source-column]'));
  const ignore = form.querySelector('[name="ignore_unused"]');
  function update(event) {
    const route = selects.find(select => select.dataset.mappingTarget === 'route');
    const departure = selects.find(select => select.dataset.mappingTarget === 'departure');
    const destination = selects.find(select => select.dataset.mappingTarget === 'destination');
    if (route && departure && destination) {
      if (!route.value && departure.value && destination.value) route.value = 'airports';
      else if (route.value === 'airports' && !departure.value && !destination.value) route.value = '';
    }
    const usage = new Map(), moved = new Set();
    const helperTargets = ['departure', 'destination', 'block out', 'block in'];
    const blockOutInput = selects.find(select => select.dataset.mappingTarget === 'block out');
    const blockInInput = selects.find(select => select.dataset.mappingTarget === 'block in');
    for (const select of selects) {
      if (!/^\d+$/.test(select.value)) continue;
      let label = select.closest('[data-mapping-row]').dataset.mappingLabel;
      if (['departure', 'destination'].includes(select.dataset.mappingTarget)) {
        if (route?.value !== 'airports' || !departure?.value || !destination?.value) continue;
        label = 'Route';
      } else if (['block out', 'block in'].includes(select.dataset.mappingTarget)) {
        if (!blockOutInput?.value || !blockInInput?.value) continue;
        label = 'Duration';
      }
      if (!helperTargets.includes(select.dataset.mappingTarget)) moved.add(select.value);
      for (const index of [select.value, ...(dependencies[select.value] || []).map(String)]) {
        if (!usage.has(index)) usage.set(index, new Set());
        usage.get(index).add(label);
      }
    }
    const duration = selects.find(select => select.dataset.mappingTarget === 'duration');
    const blockOut = selects.find(select => select.dataset.mappingTarget === 'block out');
    const blockIn = selects.find(select => select.dataset.mappingTarget === 'block in');
    if (duration && !duration.value && blockOut?.value && blockIn?.value) {
      duration.value = 'block_times';
      duration.closest('[data-mapping-row]').querySelector('[data-mapping-status]').textContent = 'Calculated from block times';
    }
    const blockOptions = form.querySelector('[data-block-options]');
    if (blockOptions) blockOptions.hidden = !(blockOut?.value || blockIn?.value || duration?.value === 'block_times');
    const differenceOption = form.querySelector('[data-block-difference-option]');
    if (differenceOption) differenceOption.hidden = duration?.value === 'block_times';
    if (event) {
      const difference = form.querySelector('[name="confirm_block_difference"]');
      if (difference) difference.checked = false;
      if (['block out', 'block in'].includes(event.target.dataset?.mappingTarget)) {
        const overnight = form.querySelector('[name="confirm_overnight"]');
        if (overnight) overnight.checked = false;
      }
    }
    let hasNumeric = false, fractional = false, over30 = false, durationOver30 = false;
    for (const select of selects) {
      if (!hourFields.includes(select.dataset.mappingTarget)) continue;
      let info = formats[select.value] || {};
      if (select.value === 'constant') {
        const value = select.closest('[data-mapping-row]').querySelector('[data-mapping-constant] input').value.trim();
        info = {numeric: /^\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(value) && Number(value) > 0,
                fractional: Number(value) > 0 && value.includes('.'), over30: Number(value) > 30, samples: [value]};
      }
      if (nativeTimes || ['duration', 'night', 'instrument', 'simulated instrument'].includes(select.dataset.mappingTarget)) {
        hasNumeric ||= !!info.numeric;
        fractional ||= !!info.fractional;
        over30 ||= !!info.over30;
        if (select.dataset.mappingTarget === 'duration') durationOver30 ||= !!info.over30;
      }
    }
    const unitRow = form.querySelector('[data-time-units]');
    const clear = !hasNumeric || (fractional && !over30);
    if (unitRow) unitRow.hidden = clear;
    units.required = !clear;
    const signature = JSON.stringify(selects.map(select => [select.value, select.closest('[data-mapping-row]').querySelector('[data-mapping-constant] input')?.value]));
    if (clear) units.value = 'hours';
    else if (units.dataset?.detectionSignature !== signature && (!event || event.target !== units)) units.value = durationOver30 ? 'minutes' : '';
    if (units.dataset) units.dataset.detectionSignature = signature;
    const used = new Set(usage.keys());
    for (const select of selects) {
      const constant = select.closest('[data-mapping-row]').querySelector('[data-mapping-constant]');
      constant.hidden = select.value !== 'constant';
      const output = select.closest('[data-mapping-row]').querySelector('[data-mapping-conversion]');
      const changes = [];
      if (select.dataset.mappingTarget === 'route') {
        if (select.value === 'airports') changes.push('Departure + Destination → Route');
        else if (routeColumns.includes(select.value)) changes.push('Departure + intermediate stops + Destination → Route');
      } else if (select.dataset.mappingTarget === 'duration' && select.value === 'block_times') {
        changes.push('Block In − Block Out → decimal hours (nearest tenth)');
      } else if (hourFields.includes(select.dataset.mappingTarget) && (nativeTimes || ['duration', 'night', 'instrument', 'simulated instrument'].includes(select.dataset.mappingTarget))) {
        let info = formats[select.value] || {};
        if (select.value === 'constant') {
          const value = constant.querySelector('input').value.trim();
          info = {hhmm: /^\d{1,3}:[0-5]\d$/.test(value), numeric: /^-?\d+(?:\.\d+)?$/.test(value), samples: [value]};
        }
        if (info.hhmm) changes.push('HH:MM → decimal hours (nearest tenth)');
        if (info.numeric && units.value === 'minutes') changes.push('Minutes → decimal hours (nearest tenth)');
        for (const sample of info.samples || []) {
          let hours;
          if (/^\d{1,3}:[0-5]\d$/.test(sample)) {const [h, m] = sample.split(':').map(Number); hours = h + m / 60;}
          else if (units.value === 'minutes' && /^\d+(?:\.\d+)?$/.test(sample)) hours = Number(sample) / 60;
          if (hours !== undefined) changes.push(sample + ' → ' + (Math.round((hours + Number.EPSILON) * 10) / 10).toFixed(1) + ' h');
        }
      }
      output.textContent = changes.join('; ');
      output.hidden = !changes.length;
      const combined = select.closest('[data-mapping-row]').querySelector('[data-combined-column]');
      if (combined) {
        const active = select.value === 'airports' && departure?.value && destination?.value;
        combined.hidden = !active;
        if (active) {
          const inputs = [departure, destination];
          const inputValue = (input, row) => input.value === 'constant'
            ? input.closest('[data-mapping-row]').querySelector('[data-mapping-constant] input').value.trim()
            : row[Number(input.value)]?.trim() || '';
          combined.querySelector('[data-combined-label]').textContent = 'Combined from ' + inputs.map(input => /^\d+$/.test(input.value) ? 'column ' + (Number(input.value) + 1) : 'shared value').join(' + ');
          combined.querySelector('[data-combined-preview]').textContent = [...new Set(sampleRows.map(row => inputs.map(input => inputValue(input, row)).join('-')))].join(', ');
          select.closest('[data-mapping-row]').querySelector('[data-mapping-status]').textContent = 'Built from airports';
        }
      }
      const assigned = select.closest('[data-mapping-row]').querySelector('[data-assigned-column]');
      if (assigned) {
        const selected = /^\d+$/.test(select.value);
        assigned.hidden = !selected;
        assigned.dataset.assignedIndex = selected ? select.value : '';
        assigned.querySelector('[data-assigned-label]').textContent = selected
          ? 'Column ' + (Number(select.value) + 1) + ' · ' + select.selectedOptions[0].textContent.split(' (column ')[0] : '';
      }
    }
    let remaining = 0;
    for (const row of sourceRows) {
      row.hidden = used.has(row.dataset.sourceColumn);
      if (!row.hidden) remaining += 1;
    }
    let available = 0;
    for (const source of form.querySelectorAll('[data-drag-column]')) {
      source.hidden = moved.has(source.dataset.dragColumn);
      if (!source.hidden) available++;
      source.querySelector('[data-source-use]').textContent = used.has(source.dataset.dragColumn)
        ? 'Used → ' + Array.from(usage.get(source.dataset.dragColumn)).join(', ') : 'Not assigned';
    }
    const emptySource = form.querySelector('[data-no-source-columns]');
    if (emptySource) emptySource.hidden = available !== 0;
    if (event && event.target.matches('[data-column-map]')) {
      const select = event.target;
      select.closest('[data-mapping-row]').querySelector('[data-mapping-status]').textContent =
        select.value === 'constant' ? 'Shared value' : select.value === 'airports' ? 'Built from airports' : select.value === 'block_times' ? 'Calculated from block times' :
        select.value ? 'Selected' : select.closest('[data-mapping-row]').dataset.unmatchedReason || 'Not provided';
    }
    form.querySelector('[data-unused-count]').textContent = remaining;
    unused.hidden = remaining === 0;
    if (event && event.target.matches('[data-column-map]') && ignore) ignore.checked = false;
  }
  for (const select of selects) select.addEventListener('change', update);
  units.addEventListener('change', update);
  for (const input of form.querySelectorAll('[data-mapping-constant] input')) input.addEventListener('input', update);
  update();
  let draggedColumn = null;
  let draggedFrom = null;
  const announcement = form.querySelector('[data-mapping-announcement]');
  const targets = Array.from(form.querySelectorAll('[data-mapping-row]'));
  const unassignedZone = form.querySelector('[data-unassigned-drop]');
  function clearDrag() {
    draggedColumn = null;
    draggedFrom = null;
    unassignedZone?.classList.remove('is-drop-target');
    for (const target of targets) target.classList.remove('is-drop-target');
    for (const source of form.querySelectorAll('[data-drag-column]')) source.classList.remove('is-dragging');
  }
  for (const source of form.querySelectorAll('[data-drag-column]')) {
    source.addEventListener('dragstart', function (event) {
      draggedColumn = source.dataset.dragColumn;
      event.dataTransfer.setData('text/plain', source.querySelector('strong').textContent);
      event.dataTransfer.effectAllowed = 'move';
      source.classList.add('is-dragging');
    });
    source.addEventListener('dragend', clearDrag);
  }
  for (const target of targets) {
    const assigned = target.querySelector('[data-assigned-column]');
    const select = target.querySelector('[data-column-map]');
    if (assigned) {
      assigned.addEventListener('dragstart', function (event) {
        if (!/^\d+$/.test(select.value)) { event.preventDefault(); return; }
        draggedColumn = select.value;
        draggedFrom = select;
        event.dataTransfer.setData('text/plain', assigned.querySelector('[data-assigned-label]').textContent);
        event.dataTransfer.effectAllowed = 'move';
      });
      assigned.addEventListener('dragend', clearDrag);
      assigned.querySelector('[data-unassign-column]').addEventListener('click', function () {
        select.value = '';
        select.dispatchEvent(new Event('change', {bubbles: true}));
        select.focus();
      });
    }
    target.addEventListener('dragover', function (event) {
      if (draggedColumn === null) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      target.classList.add('is-drop-target');
    });
    target.addEventListener('dragleave', function (event) {
      if (!target.contains(event.relatedTarget)) target.classList.remove('is-drop-target');
    });
    target.addEventListener('drop', function (event) {
      if (draggedColumn === null) return;
      event.preventDefault();
      const select = target.querySelector('[data-column-map]');
      if (!Array.from(select.options).some(option => option.value === draggedColumn)) return;
      const selectedColumn = draggedColumn;
      if (draggedFrom && draggedFrom !== select) {
        draggedFrom.value = '';
        draggedFrom.dispatchEvent(new Event('change', {bubbles: true}));
      }
      select.value = selectedColumn;
      select.dispatchEvent(new Event('change', {bubbles: true}));
      announcement.textContent = select.selectedOptions[0].textContent.split(' (column ')[0] + ' assigned to ' + target.dataset.mappingLabel + '.';
      clearDrag();
    });
  }
  if (unassignedZone) {
    unassignedZone.addEventListener('dragover', function (event) {
      if (!draggedFrom) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      unassignedZone.classList.add('is-drop-target');
    });
    unassignedZone.addEventListener('dragleave', function (event) {
      if (!unassignedZone.contains(event.relatedTarget)) unassignedZone.classList.remove('is-drop-target');
    });
    unassignedZone.addEventListener('drop', function (event) {
      if (!draggedFrom) return;
      event.preventDefault();
      const label = draggedFrom.closest('[data-mapping-row]').dataset.mappingLabel;
      draggedFrom.value = '';
      draggedFrom.dispatchEvent(new Event('change', {bubbles: true}));
      announcement.textContent = 'Source column unassigned from ' + label + '.';
      clearDrag();
    });
  }
  const optional = form.querySelector('[data-optional-mappings]');
  if (optional) optional.querySelector('summary').addEventListener('dragover', function (event) {
    if (draggedColumn !== null) { event.preventDefault(); optional.open = true; }
  });
})();

(function () {
  const zone = document.querySelector('[data-file-drop]');
  if (!zone) return;
  const input = zone.querySelector('input[type="file"]');
  const status = zone.querySelector('[data-file-drop-status]');
  const maxBytes = Number(zone.dataset?.maxBytes) || 20 * 1024 * 1024;
  const maxMB = Number(zone.dataset?.maxMb) || maxBytes / (1024 * 1024);
  zone.addEventListener('dragover', function (event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
    zone.classList.add('is-drop-target');
  });
  zone.addEventListener('dragleave', function (event) {
    if (!zone.contains(event.relatedTarget)) zone.classList.remove('is-drop-target');
  });
  zone.addEventListener('drop', function (event) {
    event.preventDefault();
    zone.classList.remove('is-drop-target');
    const files = event.dataTransfer.files;
    if (files.length !== 1) { status.textContent = 'Choose one file at a time.'; return; }
    if (!/\.(csv|tsv|txt)$/i.test(files[0].name)) { status.textContent = 'Choose a CSV, TSV or TXT file.'; return; }
    if (files[0].size > maxBytes) { status.textContent = 'Choose a file no larger than ' + maxMB + ' MB.'; return; }
    try {
      input.files = files;
      input.dispatchEvent(new Event('change', {bubbles: true}));
      status.textContent = files[0].name + ' selected. Review the file to continue.';
    } catch (error) {
      status.textContent = 'Use Choose File to select this file.';
    }
  });
  input.addEventListener('change', function () {
    status.textContent = input.files.length ? input.files[0].name : '';
  });
})();
