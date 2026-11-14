const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../../../static/js/form_feedback.js'), 'utf8');

function setup(kind = '') {
  const form = new EventTarget();
  form.dataset = {submitFeedback: kind};
  const window = new EventTarget();
  const page = {tagName: 'MAIN', inert: false};
  const alreadyLocked = {tagName: 'DIV', inert: true};
  const classes = new Set();
  const body = {children: [page, alreadyLocked],
    classList: {add: name => classes.add(name), remove: name => classes.delete(name)},
    appendChild(node) { this.children.push(node); form.status = node; }};
  const button = {tagName: 'BUTTON', innerHTML: 'Save changes', value: 'save', disabled: false,
    setAttribute(name, value) { this[name] = value; }, removeAttribute(name) { delete this[name]; }};
  form.querySelectorAll = () => [button];
  form.setAttribute = (name, value) => { form[name] = value; };
  form.removeAttribute = name => { delete form[name]; };
  vm.runInNewContext(script, {window, queueMicrotask, document: {
    body, querySelectorAll: () => [form], createElement: () => ({setAttribute() {}})
  }});
  const submit = () => { const event = new Event('submit', {cancelable: true}); form.dispatchEvent(event); return event; };
  return {form, window, button, submit, page, classes, alreadyLocked};
}

test('accepted submission shows saving feedback without dropping submitter values', async () => {
  const {form, button, submit, page, classes} = setup();
  submit();
  await Promise.resolve();
  assert.equal(form.status.textContent, 'Saving changes…');
  assert.equal(form.status.hidden, false);
  assert.equal(form.status.className, 'visually-hidden');
  assert.equal(page.inert, true);
  assert.equal(classes.has('is-saving'), true);
  assert.equal(button.disabled, false);
  assert.equal(button.value, 'save');
  assert.equal(submit().defaultPrevented, true);
});

test('cancelled validation does not lock the form or claim it is saving', async () => {
  const {form, submit, page, classes} = setup();
  form.addEventListener('submit', event => event.preventDefault());
  submit();
  await Promise.resolve();
  assert.equal(form.status.hidden, true);
  assert.equal(form['aria-busy'], undefined);
  assert.equal(page.inert, false);
  assert.equal(classes.has('is-saving'), false);
});

test('async route validation reports checking and restores the form on failure', () => {
  const {form, button, page, classes, alreadyLocked} = setup();
  form.dispatchEvent(new CustomEvent('form-feedback', {detail: 'Checking route…'}));
  assert.equal(button.textContent, 'Checking route…');
  assert.equal(form.status.hidden, false);
  assert.equal(page.inert, true);
  form.dispatchEvent(new CustomEvent('form-feedback', {detail: null}));
  assert.equal(form.status.hidden, true);
  assert.equal(button.innerHTML, 'Save changes');
  assert.equal(button['aria-disabled'], undefined);
  assert.equal(page.inert, false);
  assert.equal(alreadyLocked.inert, true);
  assert.equal(classes.has('is-saving'), false);
});

test('browser back restores controls and allows submission again', async () => {
  const {form, window, button, submit, page} = setup();
  submit();
  await Promise.resolve();
  window.dispatchEvent(new Event('pageshow'));
  assert.equal(form.status.hidden, true);
  assert.equal(button['aria-disabled'], undefined);
  assert.equal(page.inert, false);
  assert.equal(submit().defaultPrevented, false);
});

test('create and delete show the appropriate message and lock only accepted submissions', async () => {
  for (const [kind, message] of [['create', 'Saving…'], ['delete', 'Deleting…']]) {
    const {form, button, submit, page} = setup(kind);
    submit();
    await Promise.resolve();
    assert.equal(button.textContent, message);
    assert.equal(form.status.textContent, message);
    assert.equal(page.inert, true);
    assert.equal(submit().defaultPrevented, true);
  }
});

test('cancelling delete confirmation leaves the page interactive', async () => {
  const {form, submit, page, classes} = setup('delete');
  form.addEventListener('submit', event => event.preventDefault());
  submit();
  await Promise.resolve();
  assert.equal(form.status.hidden, true);
  assert.equal(page.inert, false);
  assert.equal(classes.has('is-saving'), false);
});
