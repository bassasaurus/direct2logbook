const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../../../static/js/form_feedback.js'), 'utf8');

function setup() {
  const form = new EventTarget();
  const window = new EventTarget();
  const button = {tagName: 'BUTTON', innerHTML: 'Save changes', value: 'save', disabled: false,
    setAttribute(name, value) { this[name] = value; }, removeAttribute(name) { delete this[name]; }};
  form.querySelectorAll = () => [button];
  form.appendChild = node => { form.status = node; };
  form.setAttribute = (name, value) => { form[name] = value; };
  form.removeAttribute = name => { delete form[name]; };
  vm.runInNewContext(script, {window, queueMicrotask, document: {
    querySelectorAll: () => [form], createElement: () => ({setAttribute() {}})
  }});
  const submit = () => { const event = new Event('submit', {cancelable: true}); form.dispatchEvent(event); return event; };
  return {form, window, button, submit};
}

test('accepted submission shows saving feedback without dropping submitter values', async () => {
  const {form, button, submit} = setup();
  submit();
  await Promise.resolve();
  assert.equal(form.status.textContent, 'Saving changes…');
  assert.equal(form.status.hidden, false);
  assert.equal(button.disabled, false);
  assert.equal(button.value, 'save');
  assert.equal(submit().defaultPrevented, true);
});

test('cancelled validation does not lock the form or claim it is saving', async () => {
  const {form, submit} = setup();
  form.addEventListener('submit', event => event.preventDefault());
  submit();
  await Promise.resolve();
  assert.equal(form.status.hidden, true);
  assert.equal(form['aria-busy'], undefined);
});

test('async route validation reports checking and restores the form on failure', () => {
  const {form, button} = setup();
  form.dispatchEvent(new CustomEvent('form-feedback', {detail: 'Checking route…'}));
  assert.equal(button.textContent, 'Checking route…');
  assert.equal(form.status.hidden, false);
  form.dispatchEvent(new CustomEvent('form-feedback', {detail: null}));
  assert.equal(form.status.hidden, true);
  assert.equal(button.innerHTML, 'Save changes');
  assert.equal(button['aria-disabled'], undefined);
});

test('browser back restores controls and allows submission again', async () => {
  const {form, window, button, submit} = setup();
  submit();
  await Promise.resolve();
  window.dispatchEvent(new Event('pageshow'));
  assert.equal(form.status.hidden, true);
  assert.equal(button['aria-disabled'], undefined);
  assert.equal(submit().defaultPrevented, false);
});
