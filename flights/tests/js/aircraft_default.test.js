const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../../../static/js/aircraft_default.js'), 'utf8');
function setup(fetch, selected = 'C172') {
  const boxes = ['C172', '737'].map(code => ({dataset: {defaultAircraftCode: code}, checked: code === selected, disabled: true,
    addEventListener(type, handler) { this.change = handler; }}));
  const container = {dataset: {url: '/api/mobile/default-aircraft/', revision: 'baseline'}, querySelectorAll() { return boxes; }};
  const status = {classList: {toggle() {}}, hidden: true};
  const requests = [];
  vm.runInNewContext(source, {document: {
    getElementById: id => id === 'aircraft-default-controls' ? container : status,
    querySelector: () => ({value: 'csrf-token'}),
  }, crypto: {randomUUID: () => 'operation-id'}, setTimeout: () => 1, clearTimeout() {},
    fetch: async (url, options) => { requests.push({url, options}); return fetch(url, options); }});
  return {boxes, container, status, requests};
}
test('checkbox switches and clears the shared default using CSRF and a revision', async () => {
  const context = setup(async (url, options) => ({ok: true, json: async () => ({record: {aircraft_type: JSON.parse(options.body).data.aircraft_type, revision: 'new-revision'}})}));
  context.boxes[1].checked = true;
  await context.boxes[1].change();
  assert.deepEqual(context.boxes.map(box => box.checked), [false, true]);
  assert.equal(context.container.dataset.revision, 'new-revision');
  assert.equal(context.requests[0].options.headers['X-CSRFToken'], 'csrf-token');
  assert.equal(JSON.parse(context.requests[0].options.body).base_revision, 'baseline');
  context.boxes[1].checked = false;
  await context.boxes[1].change();
  assert.deepEqual(context.boxes.map(box => box.checked), [false, false]);
  assert.equal(context.boxes.some(box => box.disabled), false);
});
test('network failure restores the saved selection and leaves controls usable', async () => {
  const context = setup(async () => { throw new Error('Offline'); });
  context.boxes[1].checked = true;
  await context.boxes[1].change();
  assert.deepEqual(context.boxes.map(box => box.checked), [true, false]);
  assert.equal(context.status.textContent, 'Default not saved. Try again.');
  assert.equal(context.boxes.some(box => box.disabled), false);
});
test('conflicting mobile change is downloaded instead of silently overwritten', async () => {
  const context = setup(async (url, options) => options && options.method === 'POST' ? {ok: false, status: 409}
    : {ok: true, json: async () => ({aircraft_type: '737', revision: 'mobile-revision'})});
  context.boxes[0].checked = false;
  await context.boxes[0].change();
  assert.deepEqual(context.boxes.map(box => box.checked), [false, true]);
  assert.equal(context.container.dataset.revision, 'mobile-revision');
  assert.equal(context.status.textContent, 'Default changed. Try again.');
});
