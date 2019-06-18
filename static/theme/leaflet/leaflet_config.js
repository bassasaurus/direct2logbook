// map init
var mymap = L.map('mapid', {
  preferCanvas: true,
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

// reload on back button
if(!!window.performance && window.performance.navigation.type == 2){
window.location.reload();
}
