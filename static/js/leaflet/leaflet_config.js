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

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(mymap);

// reload on back button
if(!!window.performance && window.performance.navigation.type == 2){
window.location.reload();
}
