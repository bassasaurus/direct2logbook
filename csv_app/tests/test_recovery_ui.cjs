const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const code = fs.readFileSync(path.join(__dirname, '../static/csv_app/js/import.js'), 'utf8');

function recoveryPage(initialStatusUrl) {
  const nodes = new Map(), requests = [], navigations = [], timers = [];
  function node(key) {
    if (!nodes.has(key)) nodes.set(key, {
      attributes: {}, handlers: {}, children: [], content: '', length: 1,
      on(name, fn) {this.handlers[name] = fn; return this;},
      attr(name, value) {if (typeof name === 'object') Object.assign(this.attributes, name);
        else if (value === undefined) return this.attributes[name]; else this.attributes[name] = value; return this;},
      removeAttr() {return this;}, removeClass() {return this;}, addClass() {return this;},
      prop() {return this;}, text(value) {if (value === undefined) return this.content; this.content = value; return this;},
      append(...values) {this.children.push(...values); return this;}, val() {return 'test-value';}
    });
    return nodes.get(key);
  }
  function $(selector) {return node(selector);}
  $.ajax = function (options) {
    const request = {options}; requests.push(request);
    const chain = {done(fn) {request.done = fn; return chain;}, fail(fn) {request.fail = fn; return chain;},
      always(fn) {request.always = fn; return chain;}};
    return chain;
  };
  node('#csv-import-status').attributes['data-status-url'] = initialStatusUrl;
  const document = {getElementById() {return null;}, querySelector() {return null;}};
  const window = {location: {assign(url) {navigations.push(url);}}};
  vm.runInNewContext(code, {document, window, $, Event,
    setTimeout(fn) {timers.push(fn);}, clearTimeout() {}});
  return {nodes, requests, navigations, timers, clickImport() {node('#csv_upload').handlers.click();}};
}
const review = {status:'needs_review', message:'Correct the highlighted pair. No flights were imported.',
  review_url:'/csv/inspect/test-batch/records/', review_label:'Correct aircraft/tailnumber'};

test('a conflict during final submission returns straight to Records', () => {
  const page = recoveryPage();
  page.clickImport();
  page.requests[0].fail({status:409, responseJSON:review});
  assert.deepEqual(page.navigations, [review.review_url]);
  assert.equal(page.nodes.get('#csv_upload').content, 'Correct aircraft/tailnumber');
  assert.equal(page.requests.length, 1);
});

test('a worker conflict found by active polling returns to Records without another import request', () => {
  const page = recoveryPage();
  page.clickImport();
  page.requests[0].done({status:'queued',message:'Queued',status_url:'/status/'});
  assert.equal(page.requests.length, 2);
  page.requests[1].done(review);
  assert.deepEqual(page.navigations, [review.review_url]);
  assert.equal(page.requests.filter(request => request.options.type === 'POST').length, 1);
  assert.equal(page.timers.length, 0);
});

test('opening Upload shows a correction link without trapping the user in a redirect', () => {
  const page = recoveryPage('/status/');
  page.requests[0].done(review);
  assert.deepEqual(page.navigations, []);
  const link = page.nodes.get('<a>');
  assert.equal(link.attributes.href, review.review_url);
  assert.equal(link.content, 'Correct aircraft/tailnumber');
  assert.equal(page.requests.length, 1);
  assert.equal(page.timers.length, 0);
});
