(function () {
  'use strict';
  document.querySelectorAll('[data-aircraft-classification]').forEach(function (root) {
    if (root.dataset.classificationReady) return;
    root.dataset.classificationReady = 'true';
    var categories = JSON.parse(root.querySelector('script[type="application/json"]').textContent);
    var category = root.querySelector('[data-aircraft-category]');
    var klass = root.querySelector('[data-category-class]');
    var field = root.querySelector('[data-aircraft-class-field]');
    var warning = root.querySelector('[data-classification-warning]');
    var form = root.closest('form');
    var existing = root.dataset.existing === 'true';
    var initialCategory = root.dataset.initialCategory || '';
    var initialClass = root.dataset.initialClass || '';
    var engine = form.querySelector('[data-aircraft-engine]');
    var wake = form.querySelector('[data-aircraft-wake]');
    function checked(group) {
      return group ? Array.from(group.querySelectorAll('input[type="radio"]')).filter(function (input) { return input.checked; }).length : 0;
    }
    var initialEngineCount = checked(engine);
    var initialWakeCount = checked(wake);

    function update(rebuild) {
      var value = klass.value;
      var choices = categories[category.value];
      if (rebuild) {
        // Keep a compatible value, clear any value belonging to another category.
        // An untouched incomplete legacy selection is preserved on initial load.
        klass.replaceChildren(new Option('---------', ''));
        (choices || []).forEach(function (choice) { klass.add(new Option(choice[1], choice[0])); });
        klass.value = choices && choices.some(function (choice) { return choice[0] === value; }) ? value : '';
      }
      var changed = category.value !== initialCategory || klass.value !== initialClass;
      var noClass = choices && choices.length === 0;
      field.hidden = !choices || Boolean(noClass);
      klass.required = Boolean(choices && choices.length && (!existing || changed));
      var valid = existing && !changed || Boolean(choices && (noClass ? !klass.value
        : choices.some(function (choice) { return choice[0] === klass.value; })));
      if (warning) warning.hidden = !changed;
      if (engine) {
        engine.hidden = category.value === 'GL' || category.value === 'LTA' && klass.value === 'BALLOON';
        engine.querySelectorAll('input[type="radio"]').forEach(function (input) {
          input.disabled = engine.hidden;
          if (engine.hidden) input.checked = false;
        });
        valid = valid && (engine.hidden || checked(engine) === 1 || existing && !changed && initialEngineCount === 0 && checked(engine) === 0);
      }
      if (wake) valid = valid && (checked(wake) === 1 || existing && initialWakeCount === 0 && checked(wake) === 0);
      var launch = form.querySelector('[data-glider-capability]');
      if (launch) {
        launch.hidden = category.value !== 'GL';
        if (launch.hidden) launch.querySelector('input').checked = false;
      }
      form.querySelectorAll('[data-aircraft-equipment]').forEach(function (group) {
        var input = group.querySelector('input');
        var typeRating = input.name === 'requires_type';
        group.hidden = category.value !== 'A' && !(typeRating && (category.value === 'R' || category.value === 'PL'));
        input.disabled = group.hidden || typeRating && category.value === 'PL';
        if (typeRating && category.value === 'PL') input.checked = true;
        if (group.hidden) input.checked = false;
      });
      var equipmentGroup = form.querySelector('[data-aircraft-equipment-group]');
      if (equipmentGroup) equipmentGroup.hidden = !['A', 'R', 'PL'].includes(category.value);
      form.dataset.aircraftValid = String(valid);
      form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(function (button) {
        button.disabled = !valid;
      });
    }
    category.addEventListener('change', function () { update(true); });
    klass.addEventListener('change', function () { update(false); });
    [engine, wake].forEach(function (group) {
      if (group) group.querySelectorAll('input[type="radio"]').forEach(function (input) {
        input.addEventListener('change', function () { update(false); });
      });
    });
    update(true);
  });
}());
