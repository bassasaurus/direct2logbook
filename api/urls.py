from django.urls import path, re_path
from rest_framework.authtoken.views import obtain_auth_token
from api import views

urlpatterns = [
    path('token-auth/', obtain_auth_token,
         name='api_token_auth'),  # add to project url
    path('tailnumber_picker/<int:aircraft_pk>/', views.tailnumber_picker_view)
]