(function () {
  'use strict';
  var table = document.getElementById('logbook');
  if (!table) return;
  var hovered = null;
  var focused = null;
  var preview = null;
  var expanded = null;
  var suppressed = null;
  function flightRow(node) {
    if (!node || !node.closest) return null;
    var row = node.closest('tr');
    return row && (row.matches('[data-flight-detail]') ? row : row.flightOwner || null);
  }
  function showRemarks() {
    var row = expanded || hovered || focused;
    if (row === suppressed) row = null;
    table.querySelectorAll('[data-remarks-toggle]').forEach(function (button) {
      button.setAttribute('aria-expanded', button.closest('tr') === row ? 'true' : 'false');
    });
    if (preview && preview.flightOwner === row) return;
    if (preview) { preview.remove(); preview = null; }
    if (!row) return;
    var cell = row.querySelector('[data-flight-remarks]');
    var remarks = cell ? cell.textContent.trim() : '';
    if (!remarks || remarks === '-') return;
    preview = document.createElement('tr');
    preview.className = 'logbook-remarks-preview';
    var toggle = row.querySelector('[data-remarks-toggle]');
    if (toggle) preview.id = toggle.getAttribute('aria-controls');
    preview.flightOwner = row;
    var contentCell = document.createElement('td');
    contentCell.colSpan = row.cells.length;
    var content = document.createElement('div');
    content.className = 'logbook-remarks-content';
    var label = document.createElement('strong');
    label.textContent = 'Remarks: ';
    content.appendChild(label);
    cell.childNodes.forEach(function (node) {
      content.appendChild(node.cloneNode(true));
    });
    contentCell.appendChild(content);
    preview.appendChild(contentCell);
    row.after(preview);
  }
  table.addEventListener('mouseover', function (event) {
    hovered = flightRow(event.target);
    if (hovered !== suppressed) suppressed = null;
    showRemarks();
  });
  table.addEventListener('mouseout', function (event) {
    hovered = table.contains(event.relatedTarget) ? flightRow(event.relatedTarget) : null;
    showRemarks();
  });
  table.addEventListener('focusin', function (event) {
    focused = flightRow(event.target);
    showRemarks();
  });
  table.addEventListener('focusout', function (event) {
    focused = flightRow(event.relatedTarget);
    showRemarks();
  });
  table.addEventListener('click', function (event) {
    var toggle = event.target.closest('[data-remarks-toggle]');
    if (toggle) {
      var owner = toggle.closest('tr');
      if (expanded === owner) {
        expanded = null;
        suppressed = owner;
      } else {
        expanded = owner;
        suppressed = null;
      }
      showRemarks();
      return;
    }
    if (event.target.closest('a, button, input, select, textarea, label')) return;
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (window.getSelection().toString()) return;
    var row = event.target.closest('[data-flight-detail]');
    if (row) window.location.assign(row.dataset.flightDetail);
  });
}());
