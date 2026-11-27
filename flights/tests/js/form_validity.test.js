const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../../../static/js/form_validity.js'),'utf8');

function setup() {
  const window = new EventTarget(); window.queueMicrotask = queueMicrotask;
  const module = {exports:{}};
  vm.runInNewContext(source,{window,module});
  const form = new EventTarget(); form.dataset = {};
  const field = {name:'required',disabled:false,willValidate:true,validity:{valid:false},closest:()=>null};
  form.elements = [field]; form.elements.namedItem = name => form.elements.find(item => item.name === name);
  const button = {disabled:false,matches:()=>false,name:'action',value:'save'};
  const navigation = {disabled:false,matches:()=>true};
  const markers = [];
  form.querySelectorAll = selector => selector.startsWith('button') ? [button,navigation] : markers;
  module.exports.setupForm(form);
  return {form,field,button,navigation,markers,window,...module.exports};
}

test('all forms disable invalid submission initially and follow edits without losing action values', async () => {
  const {form,field,button} = setup();
  assert.equal(button.disabled,true);
  field.validity.valid = true;
  form.dispatchEvent(new Event('input')); await Promise.resolve();
  assert.equal(button.disabled,false);
  assert.equal(button.name,'action'); assert.equal(button.value,'save');
  field.validity.valid = false;
  form.dispatchEvent(new Event('change')); await Promise.resolve();
  assert.equal(button.disabled,true);
});

test('custom validation errors, required decisions and conditional fields participate', () => {
  const {form,field,markers,formIsValid} = setup();
  field.validity.valid = true;
  assert.equal(formIsValid(form),true);
  markers.push({disabled:false,closest:()=>null});
  assert.equal(formIsValid(form),false);
  markers[0].disabled = true;
  assert.equal(formIsValid(form),true);
  markers.length = 0;
  form.dataset.aircraftValid='false'; assert.equal(formIsValid(form),false);
  form.dataset.aircraftValid='true'; assert.equal(formIsValid(form),true);
  field.validity.valid=false; field.disabled=true;
  assert.equal(formIsValid(form),true);
  field.disabled=false; field.closest=()=>({hidden:true});
  assert.equal(formIsValid(form),true);
});

test('signature Save follows the required drawing, including Clear', () => {
  const {form,field,button} = setup(); field.validity.valid = true;
  form.dataset.signatureValid='false'; form.dispatchEvent(new Event('form-validation'));
  assert.equal(button.disabled,true);
  form.dataset.signatureValid='true'; form.dispatchEvent(new Event('form-validation'));
  assert.equal(button.disabled,false);
  form.dataset.signatureValid='false'; form.dispatchEvent(new Event('form-validation'));
  assert.equal(button.disabled,true);
});

test('Enter cannot bypass invalid fields, and review/navigation actions remain available', () => {
  const {form,navigation} = setup();
  const submit = new Event('submit',{cancelable:true}); form.dispatchEvent(submit);
  assert.equal(submit.defaultPrevented,true);
  assert.equal(navigation.disabled,false);
  const next = new Event('submit',{cancelable:true}); Object.defineProperty(next,'submitter',{value:navigation});
  form.dispatchEvent(next); assert.equal(next.defaultPrevented,false);
});

test('Back/Forward restoration recomputes validity', async () => {
  const {form,field,button,window} = setup();
  field.validity.valid = true;
  window.dispatchEvent(new Event('pageshow')); await Promise.resolve();
  assert.equal(button.disabled,false);
  field.validity.valid = false;
  window.dispatchEvent(new Event('pageshow')); await Promise.resolve();
  assert.equal(button.disabled,true);
});

test('password confirmation must match before enabling submission', () => {
  const {form,field,formIsValid} = setup(); field.validity.valid = true;
  const password={...field,name:'password1',value:'example-one'};
  const confirmation={...field,name:'password2',value:'example-two'};
  form.elements.push(password,confirmation);
  assert.equal(formIsValid(form),false);
  confirmation.value=password.value;
  assert.equal(formIsValid(form),true);
});
