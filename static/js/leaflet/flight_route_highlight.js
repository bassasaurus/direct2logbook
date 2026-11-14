(function () {
  'use strict';
  var dataNode = document.getElementById('flight-map-data');
  if (!dataNode) return;
  var data = JSON.parse(dataNode.textContent);
  var layers = Object.create(null);
  var routeLabels = Object.create(null);
  var activeLabels = null;
  var mapHover = null;
  var routeIds = Object.keys(data.routes);
  var singleRoute = routeIds.length === 1;
  var links = document.querySelectorAll('[data-flight-id], [data-route-group]');
  var hovered = null;
  var focused = null;
  function distanceUnit() {
    var selector = document.getElementById('distance-unit');
    var units = {nm: [1, 'NM'], mi: [1852 / 1609.344, 'mi'], km: [1.852, 'km']};
    return units[selector && selector.value] || units.nm;
  }
  function updateMileage(ids) {
    if (!data.mileage) return;
    var value = document.getElementById('route-mileage-value');
    var excluded = document.getElementById('route-mileage-excluded');
    if (!value || !excluded) return;
    var total = data.mileage.total_nm;
    var missing = data.mileage.unavailable;
    if (ids && ids.length) {
      var known = 0;
      total = 0;
      missing = 0;
      ids.forEach(function (id) {
        var distance = data.mileage.distances[id];
        if (typeof distance === 'number' && Number.isFinite(distance)) {
          total += distance;
          known += 1;
        } else {
          missing += 1;
        }
      });
      if (!known) total = null;
    }
    var conversion = distanceUnit();
    value.textContent = total === null ? 'Unavailable' : (total * conversion[0]).toLocaleString('en-US', {
      minimumFractionDigits: 1, maximumFractionDigits: 1
    }) + ' ' + conversion[1];
    excluded.hidden = !missing;
    excluded.textContent = missing + ' flight' + (missing === 1 ? '' : 's') + ' excluded: unresolved route';
  }
  var bounds = L.latLngBounds([]);
  var airports = L.geoJSON(data.airports, {pointToLayer: createAirportMarker}).addTo(mymap);
  if (airports.getBounds().isValid()) bounds.extend(airports.getBounds());

  // Circle bounds depend on Leaflet's projection. Establish a view before
  // adding paths, including months containing only a local A-to-A flight.
  routeIds.forEach(function (id) {
    data.routes[id].forEach(function (point) { bounds.extend(point); });
  });
  if (bounds.isValid()) {
    mymap.fitBounds(bounds, {padding: [40, 40], maxZoom: 11});
  } else {
    mymap.setView([20, 0], 2.1);
  }

  function legLabel(line, start, end) {
    // Geodesics can split at the antimeridian. Use the longer visible piece.
    var path = line.getLatLngs().reduce(function (longest, part) {
      return part.length > longest.length ? part : longest;
    }, []);
    var middle = Math.floor(path.length / 2);
    var before = mymap.project(path[middle - 1]);
    var after = mymap.project(path[middle]);
    var angle = Math.atan2(after.y - before.y, after.x - before.x) * 180 / Math.PI;
    // Keep the text upright regardless of the flight direction.
    angle = (angle + 270) % 180 - 90;
    var center = mymap.unproject(before.add(after).divideBy(2));
    var conversion = distanceUnit();
    var distance = (L.latLng(start).distanceTo(end) / 1852 * conversion[0])
      .toLocaleString('en-US', {maximumFractionDigits: 1});
    var icon = L.divIcon({
      className: '',
      iconSize: [0, 0],
      html: '<span class="position-absolute text-nowrap bg-white rounded px-1 fw-semibold" ' +
        'style="transform: translate(-50%, -50%) rotate(' + angle + 'deg)">' +
        distance + ' ' + conversion[1] + '</span>'
    });
    return L.marker(center, {icon: icon, interactive: false, keyboard: false});
  }

  function showLabels(id) {
    var labels = routeLabels[id] || null;
    if (labels === activeLabels) return;
    if (activeLabels) mymap.removeLayer(activeLabels);
    if (labels) labels.addTo(mymap);
    activeLabels = labels;
  }

  routeIds.forEach(function (id) {
    var points = data.routes[id];
    if (!points.length) return;
    var options = {color: '#496b8a', weight: 1.5, opacity: .85, interactive: false};
    var layer;
    if (points.length >= 2) {
      options.steps = 200;
      options.interactive = !singleRoute;
      var legs = [];
      var labels = [];
      for (var i = 1; i < points.length; i += 1) {
        var line = L.geodesic([[points[i - 1], points[i]]], options);
        legs.push(line);
        labels.push(legLabel(line, points[i - 1], points[i]));
      }
      layer = L.featureGroup(legs);
      routeLabels[id] = L.layerGroup(labels);
      layer.on('mouseover', function () { mapHover = id; updateHighlight(); });
      layer.on('mouseout', function () { mapHover = null; updateHighlight(); });
    } else {
      options.radius = 3000;
      layer = L.circle(points[0], options);
    }
    layers[id] = layer.addTo(mymap);
    bounds.extend(layer.getBounds());
  });
  if (singleRoute) showLabels(routeIds[0]);
  if (bounds.isValid()) {
    mymap.fitBounds(bounds, {padding: [40, 40]});
  } else {
    mymap.setView([20, 0], 2.1);
  }

  function updateHighlight() {
    var active = hovered || focused;
    var selectedIds = active && active.indexOf('group:') === 0
      ? (data.groups || {})[active.slice(6)] || [] : (Object.prototype.hasOwnProperty.call(data.routes, active) ? [active] : []);
    updateMileage(selectedIds.length ? selectedIds : mapHover ? [mapHover] : null);
    if (!selectedIds.some(function (id) { return !!layers[id]; })) active = null;
    Object.keys(layers).forEach(function (id) {
      var selected = selectedIds.indexOf(id) !== -1;
      layers[id].setStyle({
        color: selected ? '#007bff' : '#496b8a',
        weight: selected ? 4 : 1.5,
        opacity: active && !selected ? .2 : (selected ? 1 : .85)
      });
    });
    selectedIds.forEach(function (id) { if (layers[id]) layers[id].bringToFront(); });
    if (!singleRoute) showLabels(active ? (selectedIds.length === 1 ? selectedIds[0] : null) : mapHover);
    airports.bringToFront();
    Array.prototype.forEach.call(links, function (link) {
      var selected = !!active && (link.dataset.routeGroup
        ? 'group:' + link.dataset.routeGroup === active
        : selectedIds.includes(link.dataset.flightId));
      link.classList.toggle('map-route-active', selected);
    });
  }

  Array.prototype.forEach.call(links, function (link) {
    var id = link.dataset.routeGroup ? 'group:' + link.dataset.routeGroup : link.dataset.flightId;
    link.addEventListener('mouseenter', function () { hovered = id; updateHighlight(); });
    link.addEventListener('mouseleave', function () { hovered = null; updateHighlight(); });
    link.addEventListener('focus', function () { focused = id; updateHighlight(); });
    link.addEventListener('blur', function () { focused = null; updateHighlight(); });
  });
  updateMileage(null);
}());
