(function () {
  'use strict';
  var dataNode = document.getElementById('flight-map-data');
  if (!dataNode) return;
  var data = JSON.parse(dataNode.textContent);
  var layers = Object.create(null);
  var links = document.querySelectorAll('[data-flight-id]');
  var hovered = null;
  var focused = null;
  var bounds = L.latLngBounds([]);
  var airports = L.geoJSON(data.airports, {pointToLayer: createAirportMarker}).addTo(mymap);
  if (airports.getBounds().isValid()) bounds.extend(airports.getBounds());

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
    if (!layers[active]) active = null;
    Object.keys(layers).forEach(function (id) {
      var selected = id === active;
      layers[id].setStyle({
        color: selected ? '#007bff' : '#496b8a',
        weight: selected ? 4 : 1.5,
        opacity: active && !selected ? .2 : (selected ? 1 : .85)
      });
    });
    if (active) layers[active].bringToFront();
    airports.bringToFront();
    Array.prototype.forEach.call(links, function (link) {
      link.classList.toggle('map-route-active', link.dataset.flightId === active);
    });
  }

  Array.prototype.forEach.call(links, function (link) {
    var id = link.dataset.flightId;
    link.addEventListener('mouseenter', function () { hovered = id; updateHighlight(); });
    link.addEventListener('mouseleave', function () { hovered = null; updateHighlight(); });
    link.addEventListener('focus', function () { focused = id; updateHighlight(); });
    link.addEventListener('blur', function () { focused = null; updateHighlight(); });
  });
}());
