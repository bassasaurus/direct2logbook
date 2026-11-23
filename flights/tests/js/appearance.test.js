const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../../../static/js/appearance.js'), 'utf8');
function setup({ saved = null, dark = false, forced = null, blocked = false } = {}) {
  let mode;
  const attrs = {};
  const button = new EventTarget();
  button.setAttribute = (name, value) => { attrs[name] = value; };
  const system = new EventTarget(); system.matches = dark;
  const window = new EventTarget();
  window.matchMedia = () => system;
  window.localStorage = {getItem() { if (blocked) throw Error(); return saved; }, setItem(key, value) { if (blocked) throw Error(); saved = value; }};
  const document = new EventTarget();
  document.documentElement = { getAttribute(name) { return name === 'data-appearance' ? forced : mode; }, setAttribute(name, value) { mode = value; } };
  document.querySelectorAll = () => [button];
  vm.runInNewContext(script, { window, document });
  document.dispatchEvent(new Event('DOMContentLoaded'));
  return {button, attrs, system, window, mode: () => mode, saved: () => saved};
}
test('uses system mode initially and persists an explicit toggle', () => {
  const app = setup({dark:true});
  assert.equal(app.mode(), 'dark');
  assert.equal(app.attrs['aria-label'], 'Switch to light mode');
  app.button.dispatchEvent(new Event('click'));
  assert.equal(app.mode(), 'light');
  assert.equal(app.saved(), 'light');
  assert.equal(app.attrs['aria-pressed'], 'false');
  app.system.dispatchEvent(new Event('change'));
  assert.equal(app.mode(), 'light');
});
test('saved preference wins; invalid preferences fall back to system', () => {
  assert.equal(setup({saved:'light',dark:true}).mode(), 'light');
  assert.equal(setup({saved:'invalid',dark:true}).mode(), 'dark');
});
test('mobile privacy appearance overrides browser preference', () => {
  const app = setup({forced:'dark',saved:'light'});
  assert.equal(app.mode(), 'dark');
  app.button.dispatchEvent(new Event('click'));
  assert.equal(app.mode(), 'dark');
});
test('blocked browser storage does not prevent toggling', () => {
  const app = setup({blocked:true});
  app.button.dispatchEvent(new Event('click'));
  assert.equal(app.mode(), 'dark');
});
test('system and cross-tab changes update appearance appropriately', () => {
  const app = setup();
  app.system.matches = true; app.system.dispatchEvent(new Event('change'));
  assert.equal(app.mode(), 'dark');
  const event = new Event('storage'); event.key='d2lb.web.appearance'; event.newValue='light';
  app.window.dispatchEvent(event);
  assert.equal(app.mode(), 'light');
});
