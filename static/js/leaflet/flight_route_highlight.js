(function () {
  'use strict';
  var dataNode = document.getElementById('flight-map-data');
  if (!dataNode) return;
  var data = JSON.parse(dataNode.textContent);
  var layers = Object.create(null);
  var links = document.querySelectorAll('[data-flight-id], [data-route-group]');
  var hovered = null;
  var focused = null;
  var bounds = L.latLngBounds([]);
  var airports = L.geoJSON(data.airports, {pointToLayer: createAirportMarker}).addTo(mymap);
  if (airports.getBounds().isValid()) bounds.extend(airports.getBounds());

  // Circle bounds depend on Leaflet's projection. Establish a view before
  // adding paths, including months containing only a local A-to-A flight.
  Object.keys(data.routes).forEach(function (id) {
    data.routes[id].forEach(function (point) { bounds.extend(point); });
  });
  if (bounds.isValid()) {
    mymap.fitBounds(bounds, {padding: [40, 40], maxZoom: 11});
  } else {
    mymap.setView([20, 0], 2.1);
  }

  Object.keys(data.routes).forEach(function (id) {
    var points = data.routes[id];
    if (!points.length) return;
    var options = {color: '#496b8a', weight: 1.5, opacity: .85, interactive: false};
    var layer;
    if (points.length >= 2) {
      options.steps = 200;
      layer = L.geodesic([points], options);
    } else {
      options.radius = 3000;
      layer = L.circle(points[0], options);
    }
    layers[id] = layer.addTo(mymap);
    bounds.extend(layer.getBounds());
  });
  if (bounds.isValid()) {
    mymap.fitBounds(bounds, {padding: [40, 40]});
  } else {
    mymap.setView([20, 0], 2.1);
  }

  function updateHighlight() {
    var active = hovered || focused;
    var selectedIds = active && active.indexOf('group:') === 0
      ? (data.groups || {})[active.slice(6)] || [] : (layers[active] ? [active] : []);
    if (!selectedIds.length) active = null;
    Object.keys(layers).forEach(function (id) {
      var selected = selectedIds.indexOf(id) !== -1;
      layers[id].setStyle({
        color: selected ? '#007bff' : '#496b8a',
        weight: selected ? 4 : 1.5,
        opacity: active && !selected ? .2 : (selected ? 1 : .85)
      });
    });
    selectedIds.forEach(function (id) { if (layers[id]) layers[id].bringToFront(); });
    airports.bringToFront();
    Array.prototype.forEach.call(links, function (link) {
      link.classList.toggle('map-route-active', (link.dataset.routeGroup ? 'group:' + link.dataset.routeGroup : link.dataset.flightId) === active);
    });
  }

  Array.prototype.forEach.call(links, function (link) {
    var id = link.dataset.routeGroup ? 'group:' + link.dataset.routeGroup : link.dataset.flightId;
    link.addEventListener('mouseenter', function () { hovered = id; updateHighlight(); });
    link.addEventListener('mouseleave', function () { hovered = null; updateHighlight(); });
    link.addEventListener('focus', function () { focused = id; updateHighlight(); });
    link.addEventListener('blur', function () { focused = null; updateHighlight(); });
  });
}());
