from django.urls import path, re_path
from rest_framework.authtoken.views import obtain_auth_token
from api import views

urlpatterns = [
    path('token-auth/', obtain_auth_token,
         name='api_token_auth'),  # add to project url
    re_path('^tailnumbers/(?P<aircraft_pk>.+)/$', views.TailNumberViewSet, name='tailnumbers_filtered')
]