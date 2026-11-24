const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../../static/js/aircraft_classification.js'), 'utf8');
const choices = { A: [['SEL', 'Single-Engine Land'], ['MEL', 'Multi-Engine Land'], ['SES', 'Single-Engine Sea'], ['MES', 'Multi-Engine Sea']],
  R: [['HELO', 'Helicopter'], ['GYRO', 'Gyroplane']], GL: [], PL: [], LTA: [['BALLOON', 'Balloon'], ['AIRSHIP', 'Airship']] };

function setup(categoryValue = '', classValue = '', existing = false) {
  const select = value => ({ value, options: [], required: false,
    replaceChildren(...options) { this.options = options; }, add(option) { this.options.push(option); },
    addEventListener(type, listener) { this.change = listener; } });
  const category = select(categoryValue), klass = select(classValue);
  const field = { hidden: false }, warning = { hidden: true }, button = { disabled: false };
  const radios = [true, false, false].map(checked => ({checked, disabled: false, addEventListener(type, listener) { this.change = listener; }}));
  const engine = {hidden: false, querySelectorAll: () => radios};
  const launchInput = {checked: true};
  const launch = {hidden: true, querySelector: () => launchInput};
  const flags = ['requires_type', 'compleks', 'high_performance', 'tailwheel'].map(name => { const input = {name, checked: true, disabled: false}; return {hidden: false, input, querySelector: () => input}; });
  const form = { querySelectorAll: selector => selector === '[data-aircraft-equipment]' ? flags : [button], querySelector: selector => selector === '[data-aircraft-engine]' ? engine : selector === '[data-glider-capability]' ? launch : null };
  const root = { dataset: { existing: String(existing), initialCategory: categoryValue, initialClass: classValue },
    closest: () => form, querySelector: selector => ({
      'script[type="application/json"]': { textContent: JSON.stringify(choices) },
      '[data-aircraft-category]': category, '[data-category-class]': klass,
      '[data-aircraft-class-field]': field, '[data-classification-warning]': warning,
    })[selector] };
  function Option(label, value) { this.label = label; this.value = value; }
  vm.runInNewContext(source, { document: { querySelectorAll: () => [root] }, Option });
  return { category, klass, field, warning, button, engine, radios, launch, flags };
}

test('new aircraft requires a category and a class when that category has classes', () => {
  const ui = setup();
  assert.equal(ui.button.disabled, true);
  ui.category.value = 'LTA'; ui.category.change();
  assert.equal(ui.klass.required, true);
  assert.equal(ui.button.disabled, true);
  assert.deepEqual(ui.klass.options.map(option => option.value), ['', 'BALLOON', 'AIRSHIP']);
  ui.klass.value = 'BALLOON'; ui.klass.change();
  assert.equal(ui.button.disabled, false);
});

test('selecting Glider or Powered-Lift clears class, hides it and removes its required constraint', () => {
  for (const category of ['GL', 'PL']) {
    const ui = setup('A', 'SEL', true);
    ui.category.value = category; ui.category.change();
    assert.equal(ui.klass.value, '');
    assert.equal(ui.klass.required, false);
    assert.equal(ui.field.hidden, true);
    assert.equal(ui.button.disabled, false);
    assert.equal(ui.warning.hidden, false);
  }
});

test('cross-category changes require a new compatible class, while unchanged legacy blanks can save', () => {
  const ui = setup('A', '', true);
  assert.equal(ui.button.disabled, false);
  assert.equal(ui.klass.required, false);
  ui.category.value = 'R'; ui.category.change();
  assert.equal(ui.klass.required, true);
  assert.equal(ui.button.disabled, true);
  assert.deepEqual(ui.klass.options.map(option => option.value), ['', 'HELO', 'GYRO']);
  ui.klass.value = 'GYRO'; ui.klass.change();
  assert.equal(ui.button.disabled, false);
  ui.category.value = 'A'; ui.category.change();
  assert.equal(ui.klass.value, '');
  assert.equal(ui.button.disabled, false); // Original incomplete classification restored.
  assert.equal(ui.warning.hidden, true);
});

test('engine controls are hidden and cleared for Glider and Balloon, and restored for Airship', () => {
  const ui = setup('A', 'SEL');
  ui.category.value = 'GL'; ui.category.change();
  assert.equal(ui.engine.hidden, true);
  assert.equal(ui.radios.every(input => !input.checked && input.disabled), true);
  assert.equal(ui.launch.hidden, false);
  ui.category.value = 'LTA'; ui.category.change();
  ui.klass.value = 'BALLOON'; ui.klass.change();
  assert.equal(ui.engine.hidden, true);
  assert.equal(ui.launch.hidden, true);
  ui.klass.value = 'AIRSHIP'; ui.klass.change();
  assert.equal(ui.engine.hidden, false);
  assert.equal(ui.radios.every(input => !input.disabled), true);
  assert.equal(ui.button.disabled, true);
  ui.radios[2].checked = true; ui.radios[2].change();
  assert.equal(ui.button.disabled, false);
});


test('category changes hide and clear inapplicable equipment controls', () => {
  const ui = setup('A', 'SEL');
  ui.category.value = 'GL'; ui.category.change();
  assert.equal(ui.flags.every(group => group.hidden && group.input.disabled && !group.input.checked), true);
  ui.category.value = 'PL'; ui.category.change();
  for (const group of ui.flags) {
    assert.equal(group.hidden, group.input.name !== 'requires_type');
    assert.equal(group.input.disabled, true);
    assert.equal(group.input.checked, group.input.name === 'requires_type');
  }
  ui.category.value = 'LTA'; ui.category.change();
  assert.equal(ui.flags.every(group => group.hidden && group.input.disabled && !group.input.checked), true);
  ui.klass.value = 'AIRSHIP'; ui.klass.change();
  assert.equal(ui.flags.every(group => group.hidden && group.input.disabled && !group.input.checked), true);
});


test('rotorcraft only offers type rating and switching back to airplane restores optional choices', () => {
  const ui = setup('A', 'SEL');
  ui.category.value = 'R'; ui.category.change();
  for (const group of ui.flags) {
    assert.equal(group.hidden, group.input.name !== 'requires_type');
    assert.equal(group.input.disabled, group.hidden);
  }
  ui.category.value = 'A'; ui.category.change();
  assert.equal(ui.flags.every(group => !group.hidden && !group.input.disabled), true);
});
