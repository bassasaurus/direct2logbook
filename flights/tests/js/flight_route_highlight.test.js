const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../../../static/js/leaflet/flight_route_highlight.js'), 'utf8');

function render(routes) {
  let ready = false;
  const paths = [];
  const links = Object.keys(routes).map(function (id) {
    return {
      dataset: {flightId: id}, handlers: {}, selected: false,
      classList: {toggle: function () {}},
      addEventListener: function (name, handler) { this.handlers[name] = handler; }
    };
  });
  links.forEach(function (link) {
    link.classList.toggle = function (name, value) { link.selected = value; };
  });
  function bounds() {
    return {
      valid: false,
      extend: function (point) { this.valid = this.valid || !!point.valid || Array.isArray(point); return this; },
      isValid: function () { return this.valid; }
    };
  }
  const airportBounds = bounds();
  const airports = {addTo: function () { return this; }, getBounds: () => airportBounds, bringToFront: function () {}};
  function layer(kind, points, options) {
    const item = {
      kind: kind, points: points, options: options,
      addTo: function () { paths.push(this); return this; },
      getBounds: function () {
        if (kind === 'circle' && !ready) throw new Error('Circle projection used before map initialization');
        return {valid: true};
      },
      setStyle: function (style) { Object.assign(this.options, style); },
      bringToFront: function () {}
    };
    return item;
  }
  const map = {
    fitBounds: function () { ready = true; },
    setView: function () { ready = true; }
  };
  vm.runInNewContext(script, {
    document: {
      getElementById: () => ({textContent: JSON.stringify({routes: routes, airports: {features: []}})}),
      querySelectorAll: () => links
    },
    mymap: map, createAirportMarker: function () {},
    L: {
      latLngBounds: bounds, geoJSON: () => airports,
      circle: (points, options) => layer('circle', points, options),
      geodesic: (points, options) => layer('geodesic', points, options)
    }
  });
  return {paths, links, ready};
}

test('local single-airport flight initializes map before measuring circle bounds', function () {
  const result = render({'13553': [[30.06, -95.55]]});
  assert.equal(result.ready, true);
  assert.equal(result.paths[0].kind, 'circle');
  result.links[0].handlers.mouseenter();
  assert.equal(result.paths[0].options.weight, 4);
  result.links[0].handlers.mouseleave();
  assert.equal(result.paths[0].options.weight, 1.5);
});

test('hover and keyboard focus highlight only the matching flight', function () {
  const result = render({'10': [[10, 20], [30, 40]], '11': [[30, 40], [50, 60]]});
  assert.equal(result.paths.length, 2);
  result.links[0].handlers.mouseenter();
  assert.equal(result.paths[0].options.color, '#007bff');
  assert.equal(result.paths[1].options.opacity, .2);
  assert.equal(result.links[0].selected, true);
  result.links[0].handlers.mouseleave();
  assert.equal(result.paths[1].options.opacity, .85);
  result.links[1].handlers.focus();
  assert.equal(result.paths[1].options.weight, 4);
  result.links[1].handlers.blur();
  assert.equal(result.paths[1].options.weight, 1.5);
});

test('missing route coordinates still initialize a usable map', function () {
  const result = render({'10': []});
  assert.equal(result.ready, true);
  assert.equal(result.paths.length, 0);
  result.links[0].handlers.mouseenter();
  assert.equal(result.links[0].selected, false);
});
