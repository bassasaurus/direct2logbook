const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const script = fs.readFileSync(require('node:path').join(__dirname, '../../../static/js/signature_strokes.js'), 'utf8');

function capture() {
  const form = new EventTarget();
  form.dataset = {};
  form.elements = { strokes: { value: '' }, stroke_aspect_ratio: { value: '' } };
  const clear = new EventTarget();
  const input = { value: '' };
  const wrapper = { clientWidth: 600, clientHeight: 300 };
  const container = { querySelector: selector => selector.startsWith('input') ? input : clear };
  const canvas = { id: 'id_signature-pad', dataset: {}, addEventListener() {},
    closest: selector => selector === 'form' ? form : selector === '.signature-pad-container' ? container : wrapper,
    getContext: () => ({ scale() {} }) };
  let pad;
  class Pad {
    constructor() { pad = this; this.data = []; }
    addEventListener(type, listener) { this[type] = listener; }
    isEmpty() { return !this.data.length; }
    clear() { this.data = []; }
    toData() { return this.data; }
    fromData(data) { this.data = data; }
    toDataURL() { throw new Error('The capture must not submit a PNG'); }
  }
  const window = new EventTarget(); window.devicePixelRatio = 2;
  vm.runInNewContext(script, { SignaturePad: Pad, window, console, setTimeout, clearTimeout, Event,
    document: { addEventListener: (_, callback) => callback(), querySelectorAll: () => [canvas] } });
  return { form, pad, clear, input, canvas };
}

test('submits normalized strokes from the displayed canvas, not retina pixels or a PNG', () => {
  const { form, pad, input } = capture();
  pad.data = [{ points: [{ x: 60, y: 120 }, { x: 300, y: 240 }] }];
  form.dispatchEvent(new Event('submit'));
  assert.deepEqual(JSON.parse(form.elements.strokes.value), [[[.1, .4], [.5, .8]]]);
  assert.equal(form.elements.stroke_aspect_ratio.value, 2);
  assert.equal(input.value, '');
});

test('clearing the drawing removes previously submitted coordinates', () => {
  const { form, pad, clear } = capture();
  pad.data = [{ points: [{ x: 60, y: 120 }, { x: 300, y: 240 }] }];
  form.dispatchEvent(new Event('submit'));
  clear.dispatchEvent(new Event('click'));
  assert.equal(form.elements.strokes.value, '');
});


test('signature validity follows drawing and clearing', () => {
  const {form,pad,clear} = capture();
  assert.equal(form.dataset.signatureValid,'false');
  pad.data = [{points:[{x:1,y:1}]}];
  pad.endStroke();
  assert.equal(form.dataset.signatureValid,'true');
  clear.dispatchEvent(new Event('click'));
  assert.equal(form.dataset.signatureValid,'false');
});
