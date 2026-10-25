// Shared airport styling for Leaflet maps. Render airport data as text, not HTML.
function createAirportMarker(feature, latlng) {
  var airport = feature.properties || {};
  var code = airport.iata || airport.icao || 'Airport';
  var iconContent = document.createElement('span');
  iconContent.className = 'airport-marker-content';
  var dot = document.createElement('span');
  dot.className = 'airport-marker-dot';
  var label = document.createElement('span');
  label.className = 'airport-marker-label';
  label.textContent = code;
  iconContent.appendChild(dot);
  iconContent.appendChild(label);

  var marker = L.marker(latlng, {
    icon: L.divIcon({
      className: 'airport-marker',
      html: iconContent.outerHTML,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
      popupAnchor: [0, -32],
    }),
    keyboard: true,
    riseOnHover: true,
    title: code + ' — ' + (airport.name || 'Airport'),
  });

  var details = document.createElement('div');
  details.className = 'airport-details';
  function addLine(className, value) {
    if (value === null || value === undefined || value === '') return;
    var line = document.createElement('div');
    line.className = className;
    line.textContent = value;
    details.appendChild(line);
  }
  addLine('airport-details-name', airport.name || code);
  addLine('airport-details-codes', [airport.iata, airport.icao].filter(Boolean).join(' · '));
  addLine('airport-details-location', [airport.city, airport.state, airport.country].filter(Boolean).join(', '));
  if (airport.elevation !== null && airport.elevation !== undefined && airport.elevation !== '') {
    addLine('airport-details-elevation', 'Elevation ' + airport.elevation + ' ft');
  }
  marker.bindPopup(details, {
    className: 'airport-details-popup',
    closeButton: false,
    autoPan: false,
    minWidth: 160,
    maxWidth: 240,
  });
  // Leaflet's normal click handler retains tap support on touch devices.
  if (window.matchMedia('(any-hover: hover)').matches) {
    marker.on('mouseover', function () { marker.openPopup(); });
    marker.on('mouseout', function () { marker.closePopup(); });
  }
  marker.on('add', function () {
    var element = marker.getElement();
    element.setAttribute('aria-label', code + ' — ' + (airport.name || 'Airport'));
    L.DomEvent.on(element, 'focus', function () { marker.openPopup(); });
    L.DomEvent.on(element, 'blur', function () { marker.closePopup(); });
  });
  return marker;
}
