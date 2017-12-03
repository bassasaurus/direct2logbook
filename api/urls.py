from django.conf.urls import url, include
from . import views
from rest_framework import routers

router = routers.DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'groups', views.GroupViewSet)
router.register(r'flights', views.FlightViewSet)
router.register(r'aircraft', views.AircraftViewSet)
router.register(r'tailnumber', views.TailNumberViewSet)
router.register(r'aircraft_category', views.AircraftCategoryViewSet)
router.register(r'aircraft_class', views.AircraftClassViewSet)
router.register(r'approaches', views.ApproachViewSet)

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework'))
]
