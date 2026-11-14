const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../../../static/js/route_airport_check.js'), 'utf8');

test('unchanged checked routes submit directly and edited routes are checked again', async () => {
  const node = () => ({classList: {add() {}, remove() {}, toggle() {}}, setAttribute() {}, removeAttribute() {}});
  const form = new EventTarget();
  const input = Object.assign(new EventTarget(), node(), {value: 'KAAA-KBBB', form, setCustomValidity() {}});
  const feedback = Object.assign(node(), {dataset: {checkUrl: '/check/'}, replaceChildren() {}, appendChild() {}});
  const hidden = {value: '{}'};
  let requests = 0, nativeSubmits = 0;
  form.requestSubmit = () => { nativeSubmits++; form.dispatchEvent(new Event('submit', {cancelable: true})); };
  vm.runInNewContext(script, {AbortController, CustomEvent, clearTimeout, window: {setTimeout},
    document: {getElementById: id => ({route: input, 'route-airport-feedback': feedback, id_airport_choices: hidden})[id], createElement: node},
    fetch: async () => { requests++; return {ok: true, json: async () => ({entries: [
      {code: 'KAAA', status: 'recognized', airport: {name: 'Airport A'}}
    ]})}; }
  });
  await new Promise(setImmediate);
  assert.equal(requests, 1);
  const first = new Event('submit', {cancelable: true});
  form.dispatchEvent(first);
  await new Promise(setImmediate);
  assert.equal(first.defaultPrevented, false);
  assert.equal(requests, 1);
  assert.equal(nativeSubmits, 0);
  input.value = 'KAAA-KCCC';
  input.dispatchEvent(new Event('input'));
  const edited = new Event('submit', {cancelable: true});
  form.dispatchEvent(edited);
  await new Promise(setImmediate);
  assert.equal(edited.defaultPrevented, true);
  assert.equal(requests, 2);
  assert.equal(nativeSubmits, 1);
});
