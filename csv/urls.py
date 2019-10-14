from django.conf.urls import url, include

from csv.views import *

urlpatterns = [

    url(r'^csv_output/$', csv_view, name='csv'),
    ]
