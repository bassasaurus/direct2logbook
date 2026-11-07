(function () {
  'use strict';
  var input = document.getElementById('aircraft-filter');
  if (!input) return;
  var groups = Array.from(document.querySelectorAll('[data-aircraft-group]'));
  var unassignedAlert = document.getElementById('aircraft-unassigned-alert');
  var unassigned = Array.from(document.querySelectorAll('[data-aircraft-unassigned]'));
  function normalize(value) {
    return value.toUpperCase().replace(/[\s-]/g, '');
  }
  function filter() {
    var query = normalize(input.value);
    var matches = 0;
    groups.forEach(function (group) {
      var typeMatches = normalize(group.querySelector('[data-aircraft-type]').textContent).includes(query);
      var visible = false;
      group.querySelectorAll('[data-tailnumber]').forEach(function (link) {
        var show = typeMatches || normalize(link.textContent).includes(query);
        link.hidden = !show;
        visible = visible || show;
      });
      group.hidden = !visible;
      if (visible) matches += 1;
    });
    var hasUnassignedMatch = false;
    unassigned.forEach(function (row) {
      var show = normalize(row.querySelector('a').textContent).includes(query);
      row.hidden = !show;
      if (show) {
        hasUnassignedMatch = true;
        matches += 1;
      }
    });
    if (unassignedAlert) unassignedAlert.hidden = !hasUnassignedMatch;
    document.getElementById('aircraft-filter-empty').hidden = !query || matches > 0;
  }
  input.addEventListener('input', filter);
  document.getElementById('aircraft-filter-clear').addEventListener('click', function () {
    input.value = '';
    filter();
    input.focus();
  });
  filter();
}());
