// Run with node --test csv_app/tests/test_import_ui.cjs (no extra dependencies).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const code = fs.readFileSync(path.join(__dirname, '../static/csv_app/js/import.js'), 'utf8');

function playground(maxBytes = 2 * 1024 * 1024) {
  const input = new EventTarget();
  input.files = [];
  let changes = 0;
  input.addEventListener('change', () => changes++);
  const status = {textContent: ''};
  const zone = new EventTarget();
  zone.dataset = {maxBytes:String(maxBytes),maxMb:String(maxBytes/(1024*1024))};
  zone.classList = {add() {}, remove() {}};
  zone.contains = () => false;
  zone.querySelector = selector => selector === 'input[type="file"]' ? input : status;
  const document = {getElementById: () => null, querySelector: () => zone};
  const $ = () => ({on() {}, attr() { return undefined; }, length: 0});
  vm.runInNewContext(code, {document, $, Event});
  return {input, status, changes: () => changes, drop(files) {
    const event = new Event('drop', {cancelable: true});
    event.dataTransfer = {files};
    zone.dispatchEvent(event);
    assert.equal(event.defaultPrevented, true);
  }};
}

test('dropping a supported file selects it and notifies the file-picker workflow', () => {
  const page = playground();
  const file = {name: 'export.tsv', size: 128};
  page.drop([file]);
  assert.equal(page.input.files[0], file);
  assert.equal(page.changes(), 1);
  assert.match(page.status.textContent, /export.tsv selected/);
});

test('multiple files do not replace an existing choice', () => {
  const page = playground();
  const original = {name: 'original.csv', size: 128};
  page.drop([original]);
  page.drop([{name: 'one.csv', size: 10}, {name: 'two.csv', size: 10}]);
  assert.equal(page.input.files[0], original);
  assert.equal(page.changes(), 1);
  assert.match(page.status.textContent, /one file at a time/);
});

test('oversized or unsupported drops are rejected without selecting a file', () => {
  const page = playground();
  page.drop([{name: 'picture.png', size: 10}]);
  assert.match(page.status.textContent, /CSV, TSV or TXT/);
  page.drop([{name: 'large.csv', size: 2 * 1024 * 1024 + 1}]);
  assert.match(page.status.textContent, /2 MB/);
  assert.equal(page.changes(), 0);
});

test('picker failure offers the normal Choose File fallback', () => {
  const page = playground();
  Object.defineProperty(page.input, 'files', {get: () => [], set() {throw new Error('Unsupported');}});
  page.drop([{name: 'export.csv', size: 128}]);
  assert.match(page.status.textContent, /Use Choose File/);
  assert.equal(page.changes(), 0);
});

function mappingPlayground(durationFormat = {numeric: true}) {
  const node = () => Object.assign(new EventTarget(), {hidden: false, textContent: '',
    classList: {add() {}, remove() {}}, contains() {return false;}});
  const columns = ['PIC', 'Pilot in Command', 'Entry Duration', 'Duration'];
  const cards = columns.map((name, index) => {
    const card = node(), label = {textContent: name}, use = node();
    card.dataset = {dragColumn: String(index)};
    card.querySelector = selector => selector === 'strong' ? label : use;
    card.use = use;
    return card;
  });
  const sources = columns.map((_, index) => Object.assign(node(), {dataset: {sourceColumn: String(index)}}));
  const rows = ['PIC', 'Duration'].map((label, index) => {
    const row = node(), constant = node(), status = node(), conversion = node();
    const input = Object.assign(node(), {value: ''});
    constant.querySelector = () => input;
    row.dataset = {mappingLabel: label};
    const assigned = Object.assign(node(), {dataset: {}}), assignedLabel = node(), unassign = node();
    assigned.querySelector = selector => selector === '[data-assigned-label]' ? assignedLabel : unassign;
    row.assigned = assigned; row.unassign = unassign;
    const select = Object.assign(node(), {value: index ? '2' : '0',
      dataset: {mappingTarget: index ? 'duration' : 'pilot in command'},
      options: columns.map((name, i) => ({value: String(i), textContent: `${name} (column ${i + 1})`}))});
    Object.defineProperty(select, 'selectedOptions', {get: () => select.options.filter(option => option.value === select.value)});
    select.matches = selector => selector === '[data-column-map]';
    select.focus = () => {};
    select.closest = () => row;
    row.querySelector = selector => ({'[data-column-map]': select, '[data-mapping-constant]': constant,
      '[data-mapping-status]': status, '[data-mapping-conversion]': conversion, '[data-assigned-column]': assigned})[selector];
    row.select = select; row.conversion = conversion;
    return row;
  });
  const units = Object.assign(node(), {value: 'hours', matches() {return false;}});
  const ignore = {checked: true}, unused = node(), count = node(), announcement = node();
  const form = node(), unassignedZone = node();
  form.querySelectorAll = selector => ({'[data-column-map]': rows.map(row => row.select),
    '[data-source-column]': sources, '[data-drag-column]': cards,
    '[data-mapping-row]': rows, '[data-mapping-constant] input': []})[selector] || [];
  form.querySelector = selector => ({'[name="time_units"]': units, '[data-unused-columns]': unused,
    '[name="ignore_unused"]': ignore, '[data-unused-count]': count,
    '[data-mapping-announcement]': announcement, '[data-optional-mappings]': null, '[data-unassigned-drop]': unassignedZone})[selector];
  const json = {
    'csv-mapping-dependencies': {'2': [3]},
    'csv-column-formats': {'0': {hhmm: true}, '1': {numeric: true}, '2': durationFormat},
    'csv-hour-fields': ['duration', 'pilot in command'], 'csv-route-columns': [], 'csv-native-times': true
  };
  const document = {getElementById: id => id === 'csv-mapping-form' ? form :
    json[id] ? {textContent: JSON.stringify(json[id])} : null, querySelector: () => null};
  const $ = () => ({on() {}, attr() {}, length: 0});
  vm.runInNewContext(code, {document, $, Event});
  return {cards, sources, rows, count, ignore, units, announcement, unassignedZone,
    returnAssigned(origin) {
      const start = new Event('dragstart', {cancelable:true});
      start.dataTransfer = {setData() {}};
      rows[origin].assigned.dispatchEvent(start);
      unassignedZone.dispatchEvent(new Event('drop', {cancelable: true}));
    },
    moveAssigned(origin, target) {
      const start = new Event('dragstart', {cancelable:true});
      start.dataTransfer = {setData() {}};
      rows[origin].assigned.dispatchEvent(start);
      rows[target].dispatchEvent(new Event('drop', {cancelable: true}));
    },
    drop(index, target) {
      const start = new Event('dragstart');
      start.dataTransfer = {setData() {}};
      cards[index].dispatchEvent(start);
      const drop = new Event('drop', {cancelable: true});
      rows[target].dispatchEvent(drop);
    }};
}

test('initial matches and prepared-column dependencies are marked used', () => {
  const page = mappingPlayground();
  assert.equal(page.cards[0].use.textContent, 'Used → PIC');
  assert.equal(page.cards[1].use.textContent, 'Not assigned');
  assert.equal(page.cards[3].use.textContent, 'Used → Duration');
  assert.equal(page.cards[3].hidden, false); // Converted source inputs remain visible.
  assert.equal(page.sources[0].hidden, true);
  assert.equal(page.sources[1].hidden, false);
  assert.equal(page.count.textContent, 1);
  assert.match(page.rows[0].conversion.textContent, /HH:MM → decimal hours/);
});

test('dropping the competing PIC updates labels and unselected columns immediately', () => {
  const page = mappingPlayground();
  page.drop(1, 0);
  assert.equal(page.rows[0].select.value, '1');
  assert.equal(page.cards[1].use.textContent, 'Used → PIC');
  assert.equal(page.cards[0].use.textContent, 'Not assigned');
  assert.equal(page.sources[1].hidden, true);
  assert.equal(page.sources[0].hidden, false);
  assert.equal(page.ignore.checked, false);
  assert.equal(page.announcement.textContent, 'Pilot in Command assigned to PIC.');
});

test('changing numeric units updates conversion notes without clearing acknowledgement', () => {
  const page = mappingPlayground();
  page.units.value = 'minutes';
  page.units.dispatchEvent(new Event('change'));
  assert.match(page.rows[1].conversion.textContent, /Minutes → decimal hours/);
  assert.equal(page.ignore.checked, true);
});

function reviewPlayground() {
  const form = new EventTarget(), input = new EventTarget(), window = new EventTarget();
  input.files = [];
  const label = {textContent: ''}, progress = {hidden: true};
  const classes = new Set(['d-none']);
  const spinner = {classList: {add(value) {classes.add(value);}, remove(value) {classes.delete(value);}}};
  const attributes = new Map();
  const button = {disabled: false, setAttribute(key, value) {attributes.set(key, value);},
    removeAttribute(key) {attributes.delete(key);},
    querySelector: selector => selector === '[data-review-label]' ? label : spinner};
  form.querySelector = selector => ({'input[type="file"]': input, '#csv-inspect-submit': button,
    '[data-review-progress]': progress})[selector];
  const document = {getElementById: id => id === 'csv-preview-form' ? form : null, querySelector: () => null};
  const $ = () => ({on() {}, attr() {}, length: 0});
  vm.runInNewContext(code, {document, window, $, Event});
  return {form, input, window, label, progress, classes, button, attributes};
}

test('Review File shows progress and prevents a second submission', () => {
  const page = reviewPlayground();
  assert.equal(page.button.disabled, true);
  page.input.files = [{name: 'flights.csv'}];
  page.input.dispatchEvent(new Event('change'));
  assert.equal(page.button.disabled, false);
  page.form.dispatchEvent(new Event('submit', {cancelable: true}));
  assert.equal(page.label.textContent, 'Reviewing file…');
  assert.equal(page.button.disabled, true);
  assert.equal(page.attributes.get('aria-busy'), 'true');
  assert.equal(page.classes.has('d-none'), false);
  assert.equal(page.progress.hidden, false);
  const second = new Event('submit', {cancelable: true});
  page.form.dispatchEvent(second);
  assert.equal(second.defaultPrevented, true);
  // File selection must remain enabled for the browser's native POST payload.
  assert.notEqual(page.input.disabled, true);
});

test('Back/Forward restoration resets Review File and its spinner', () => {
  const page = reviewPlayground();
  page.input.files = [{name: 'flights.csv'}];
  page.form.dispatchEvent(new Event('submit', {cancelable: true}));
  page.window.dispatchEvent(new Event('pageshow'));
  assert.equal(page.label.textContent, 'Review file');
  assert.equal(page.button.disabled, false);
  assert.equal(page.attributes.has('aria-busy'), false);
  assert.equal(page.classes.has('d-none'), true);
  assert.equal(page.progress.hidden, true);
});


test('assigned columns leave the source palette and move between destination fields', () => {
  const page = mappingPlayground();
  assert.equal(page.cards[0].hidden, true);
  assert.equal(page.rows[0].assigned.hidden, false);
  page.moveAssigned(0, 1);
  assert.equal(page.rows[0].select.value, '');
  assert.equal(page.rows[0].assigned.hidden, true);
  assert.equal(page.rows[1].select.value, '0');
  assert.equal(page.rows[1].assigned.hidden, false);
  assert.equal(page.cards[0].hidden, true);
  assert.equal(page.cards[2].hidden, false);
});

test('unassigning an attached column returns it to Your File', () => {
  const page = mappingPlayground();
  page.rows[0].unassign.dispatchEvent(new Event('click'));
  assert.equal(page.rows[0].select.value, '');
  assert.equal(page.cards[0].hidden, false);
  assert.equal(page.rows[0].assigned.hidden, true);
});


test('clear decimal formats hide the picker and keep decimal hours', () => {
  const page = mappingPlayground({numeric: true, fractional: true, samples: ['1.5']});
  assert.equal(page.units.required, false);
  assert.equal(page.units.value, 'hours');
});

test('large durations suggest minutes and show a conversion example', () => {
  const page = mappingPlayground({numeric: true, over30: true, samples: ['90']});
  assert.equal(page.units.required, true);
  assert.equal(page.units.value, 'minutes');
  assert.match(page.rows[1].conversion.textContent, /90 → 1.5 h/);
  page.units.value = 'hours';
  page.units.dispatchEvent(new Event('change'));
  assert.equal(page.units.value, 'hours');
});

test('whole numeric durations ask for units without a default', () => {
  const page = mappingPlayground({numeric: true, whole: true, samples: ['25']});
  assert.equal(page.units.required, true);
  assert.equal(page.units.value, '');
});


test('dragging an assigned column back to Your File clears its mapping and returns the source', () => {
  const page = mappingPlayground();
  page.returnAssigned(0);
  assert.equal(page.rows[0].select.value, '');
  assert.equal(page.rows[0].assigned.hidden, true);
  assert.equal(page.cards[0].hidden, false);
  assert.equal(page.sources[0].hidden, false);
  assert.equal(page.ignore.checked, false);
  assert.equal(page.announcement.textContent, 'Source column unassigned from PIC.');
  // It can be assigned again immediately.
  page.drop(0, 0);
  assert.equal(page.rows[0].select.value, '0');
  assert.equal(page.cards[0].hidden, true);
});

test('unassigned panel ignores unrelated drops', () => {
  const page = mappingPlayground();
  const drop = new Event('drop', {cancelable: true});
  page.unassignedZone.dispatchEvent(drop);
  assert.equal(drop.defaultPrevented, false);
  assert.equal(page.rows[0].select.value, '0');
});


test('drop validation uses the server-provided byte limit', () => {
  const page=playground(20*1024*1024);
  page.drop([{name:'large-valid.csv',size:3*1024*1024}]);
  assert.equal(page.changes(),1);
  page.drop([{name:'too-large.csv',size:20*1024*1024+1}]);
  assert.match(page.status.textContent,/20 MB/);
  assert.equal(page.changes(),1);
});
