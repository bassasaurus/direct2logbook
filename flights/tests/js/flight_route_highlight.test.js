const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../../../static/js/leaflet/flight_route_highlight.js'), 'utf8');

function render(routes, groups) {
  let ready = false;
  const paths = [];
  const visibleLabels = new Set();
  const links = Object.keys(routes).map(function (id) {
    return {
      dataset: {flightId: id}, handlers: {}, selected: false,
      classList: {toggle: function () {}},
      addEventListener: function (name, handler) { this.handlers[name] = handler; }
    };
  });
  Object.keys(groups || {}).forEach(function (year) {
    links.push({dataset: {routeGroup: year}, handlers: {}, classList: {},
      addEventListener: function (name, handler) { this.handlers[name] = handler; }});
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
      on: function () { return this; },
      getLatLngs: () => points,
      setStyle: function (style) { Object.assign(this.options, style); },
      bringToFront: function () {}
    };
    return item;
  }
  function point(x, y) {
    return {x, y, add: other => point(x + other.x, y + other.y),
      divideBy: divisor => point(x / divisor, y / divisor)};
  }
  const map = {
    project: ([lat, lng]) => point(lng, -lat),
    unproject: ({x, y}) => [-y, x],
    removeLayer: group => visibleLabels.delete(group),
    fitBounds: function () { ready = true; },
    setView: function () { ready = true; }
  };
  vm.runInNewContext(script, {
    document: {
      getElementById: () => ({textContent: JSON.stringify({routes: routes, groups: groups, airports: {features: []}})}),
      querySelectorAll: () => links
    },
    mymap: map, createAirportMarker: function () {},
    L: {
      latLngBounds: bounds, geoJSON: () => airports,
      circle: (points, options) => layer('circle', points, options),
      geodesic: (points, options) => layer('geodesic', points, {...options}),
      featureGroup: legs => layer('route', legs, legs[0].options),
      layerGroup: markers => ({markers, addTo: function () { visibleLabels.add(this); }}),
      latLng: ([lat, lng]) => ({
        distanceTo: ([endLat, endLng]) => Math.hypot(endLat - lat, endLng - lng) * 1852
      }),
      divIcon: options => options,
      marker: (center, options) => ({center, options})
    }
  });
  return {paths, links, ready, visibleLabels};
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

test('year hover highlights all matching routes and restores them on leave', function () {
  const result = render({'10': [[10, 20], [30, 40]], '11': [[20, 30]], '12': [[40, 50]]}, {'2025': ['10', '11']});
  const year = result.links[3];
  year.handlers.mouseenter();
  assert.equal(result.paths[0].options.weight, 4);
  assert.equal(result.paths[1].options.weight, 4);
  assert.equal(result.paths[2].options.opacity, .2);
  assert.equal(year.selected, true);
  year.handlers.mouseleave();
  assert.equal(result.paths[0].options.weight, 1.5);
  assert.equal(result.paths[2].options.opacity, .85);
  year.handlers.focus();
  assert.equal(result.paths[1].options.weight, 4);
  year.handlers.blur();
  assert.equal(result.paths[1].options.weight, 1.5);
});

test('highlighted multi-leg flights show one aligned label per leg', function () {
  const result = render({'10': [[0, 0], [0, 20], [30, 20]], '11': [[0, 0], [10, 10]]});
  assert.equal(result.visibleLabels.size, 0);
  result.links[0].handlers.focus();
  const [group] = result.visibleLabels;
  assert.deepEqual(Array.from(group.markers, marker => marker.center), [[0, 10], [15, 20]]);
  assert.match(group.markers[0].options.icon.html, /rotate\(0deg\).*20 NM/);
  assert.match(group.markers[1].options.icon.html, /rotate\(-90deg\).*30 NM/);
  result.links[0].handlers.blur();
  assert.equal(result.visibleLabels.size, 0);
});
