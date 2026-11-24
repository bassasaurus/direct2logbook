const test = require('node:test');
const assert = require('node:assert/strict');
const {columnGrid, scrollEdges} = require('../../../static/js/table_interactions.js');
const cell = (colSpan = 1, rowSpan = 1) => ({colSpan, rowSpan});

test('column positions follow both levels of merged IACRA headers', () => {
  const category = cell(1, 2), picSic = cell(2), instrument = cell(1, 2);
  const pic = cell(), sic = cell(), a = cell(), b = cell(), c = cell(), d = cell();
  const positions = columnGrid([{cells: [category, picSic, instrument]}, {cells: [pic, sic]}, {cells: [a, b, c, d]}]);
  assert.deepEqual(positions.get(picSic), {start: 1, end: 3});
  assert.deepEqual(positions.get(pic), positions.get(b));
  assert.deepEqual(positions.get(sic), positions.get(c));
  assert.deepEqual(positions.get(instrument), positions.get(d));
});
test('body rowspans and full-width remarks do not shift later row columns', () => {
  const classLabel = cell(1, 2), first = cell(), second = cell(), remarks = cell(3), next = cell();
  const positions = columnGrid([{cells: [classLabel, first]}, {cells: [second]}, {cells: [remarks]}, {cells: [next]}]);
  assert.deepEqual(positions.get(second), {start: 1, end: 2});
  assert.deepEqual(positions.get(remarks), {start: 0, end: 3});
  assert.deepEqual(positions.get(next), {start: 0, end: 1});
});
test('horizontal indicators only point toward columns outside the viewport', () => {
  assert.deepEqual(scrollEdges(800, 800, 0), {left: false, right: false});
  assert.deepEqual(scrollEdges(1200, 800, 0), {left: false, right: true});
  assert.deepEqual(scrollEdges(1200, 800, 200), {left: true, right: true});
  assert.deepEqual(scrollEdges(1200, 800, 400), {left: true, right: false});
  assert.deepEqual(scrollEdges(800.5, 800, 0), {left: false, right: false});
});
