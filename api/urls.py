from django.conf.urls import url, include
from . import views
from rest_framework import routers
from rest_framework.authtoken.views import obtain_auth_token

router = routers.DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'flights', views.FlightViewSet)
router.register(r'aircraft', views.AircraftViewSet)
router.register(r'tailnumber', views.TailNumberViewSet)

urlpatterns = [
    url(r'^',
        include(router.urls)),

    url(r'^auth/login/$',
        obtain_auth_token,
        name='auth_user_login'),

    url(r'^auth/logout/$',
        LogoutUserAPIView.as_view(),
        name='auth_user_logout'),

    url(r'^api-auth/',
        include('rest_framework.urls',
        namespace='rest_framework'))
]
