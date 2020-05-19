from django.conf.urls import url, include
from . import views
from rest_framework import routers

router = routers.DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'flights', views.FlightViewSet)
router.register(r'aircraft', views.AircraftViewSet)
router.register(r'tailnumber', views.TailNumberViewSet)

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework'))
]
