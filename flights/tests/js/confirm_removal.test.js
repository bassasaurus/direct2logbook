const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../../../static/js/confirm_removal.js'), 'utf8');
function fixture(email = null) {
  const doc = new EventTarget(), modal = new EventTarget(), confirm = new EventTarget();
  const title = {}, message = {}, detail = {};
  const nodes = {'confirm-removal': modal, 'confirm-removal-submit': confirm,
    'confirm-removal-title': title, 'confirm-removal-message': message, 'confirm-removal-detail': detail};
  let posts = 0, shown = 0, focused = 0, submitter;
  const button = {isConnected: true, hasAttribute: () => true, focus: () => focused++,
    dataset: {confirmTitle: 'Remove Reminder?', confirmMessage: 'Remove from your account?', confirmDetail: '<Sample>'}};
  const form = {isConnected: true, querySelector: () => email ? {value: email} : null,
    requestSubmit(original) { submitter = original; const event = submit(original); if (!event.defaultPrevented) posts++; }};
  function submit(original = button) {
    const event = new Event('submit', {cancelable: true});
    Object.defineProperties(event, {target: {value: form}, submitter: {value: original}});
    doc.dispatchEvent(event);
    return event;
  }
  doc.getElementById = id => nodes[id];
  vm.runInNewContext(script, {document: doc, window: {bootstrap: {Modal: {getOrCreateInstance: () => ({
    show() { shown++; }, hide() {},
  })}}}});
  return {submit, confirm, modal, detail, button, state: () => ({posts, shown, focused, submitter})};
}
test('cancel, Escape or backdrop close never submit and return focus to Remove', () => {
  const f = fixture();
  assert.equal(f.submit().defaultPrevented, true);
  f.modal.dispatchEvent(new Event('hidden.bs.modal'));
  assert.equal(f.state().posts, 0);
  assert.equal(f.state().focused, 1);
  assert.equal(f.detail.textContent, '<Sample>');
});
test('confirm submits once with the original button, preserving email removal action', () => {
  const f = fixture('sample@example.com');
  f.submit();
  assert.equal(f.detail.textContent, 'sample@example.com');
  f.confirm.dispatchEvent(new Event('click'));
  f.confirm.dispatchEvent(new Event('click'));
  assert.equal(f.state().posts, 0);
  f.modal.dispatchEvent(new Event('hidden.bs.modal'));
  assert.equal(f.state().posts, 1);
  assert.equal(f.state().submitter, f.button);
});
test('other submit actions do not open the removal dialog', () => {
  const f = fixture();
  assert.equal(f.submit({hasAttribute: () => false}).defaultPrevented, false);
  assert.equal(f.state().shown, 0);
});
