// map init

var mymap = L.map('mapid', {
  minZoom: 2.1,
  maxZoom: 18,
  zoom: 15,
  zoomSnap: 0.50,
  useCache: true,
  crossOrigin: true,
  loadingControl: true,
});

L.tileLayer('https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token={accessToken}', {
  attribution: 'Map data &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery © <a href="http://mapbox.com">Mapbox</a>',
  maxZoom: 15,
  id: 'mapbox.streets',
  accessToken: 'pk.eyJ1IjoicGlnYXJrbGUiLCJhIjoiY2o3bGZ3Z2txMnB0cDJxbHhndjJkbnRvciJ9.IytedDwzW9skTCe_7d_gdQ'
  }).addTo(mymap);

// map draw airports
$.ajax({
  type: "GET",
  url: "/geojson/airports",
  dataType: 'json',
  async: true,
  success: function (data) {
    var airportsLayer = L.geoJSON(data, {
      onEachFeature: function (feature, layer) {
        layer.bindPopup('<h5>'+feature.properties.icao+'</h5>'+'<h6>'+feature.properties.iata+'</h5>'+'<hr>'+'<p>'+feature.properties.name+'</p>'+'<p>'+feature.properties.city+', '+feature.properties.state+', '+feature.properties.country+'</p>'+'<p>'+feature.properties.elevation+' ft</p>');
        }
      }).addTo(mymap);
      mymap.fitBounds(airportsLayer.getBounds(), {paddingTopLeft: [40, 40]});
      // var conditionalLayer = L.conditionalMarkers(data, {maxMarkers: 40}).addTo(mymap);
    }
  });

function filterSuccessiveDuplicatePositions(latlngs) {
  var result = [];

  if (latlngs.length > 0) {
    result.push(latlngs[0]);
  }

  for (var i = 1; i < latlngs.length; i += 1) {
    if (!L.latLng(latlngs[i]).equals(latlngs[i - 1])) {
      result.push(latlngs[i]);
    }
  }
  return result;
}

$.ajax({
  type: "GET",
  url: "/geojson/routes",
  dataType: 'json',
  async: true,
  success: function(latlngs) {
    if (filterSuccessiveDuplicatePositions(latlngs).length >= 2){
      // console.log("multiple points")
      var filtered = filterSuccessiveDuplicatePositions(latlngs);
      var Geodesic = L.geodesic([filtered], {
        weight: 1.5,
        opacity: 1,
        color: 'navy',
        steps: 200,
      }).addTo(mymap);
    }
    else{
      // console.log("single point")
      var filtered = filterSuccessiveDuplicatePositions(latlngs);
      var circle = L.circle(filtered[0], {
        radius: 3000,
        color: 'navy',

      }).addTo(mymap);
      // sets zoom to view entire circle
      var currentDiameter = L.circle(filtered[0], 3000);
      currentDiameter.addTo(mymap);
      mymap.fitBounds(currentDiameter.getBounds());
      }
    }
    });

// reload on back button
if(!!window.performance && window.performance.navigation.type == 2){
window.location.reload();
}
