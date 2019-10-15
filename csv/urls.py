from django.conf.urls import url, include

from csv.views import *

urlpatterns = [

    url(r'^csv/output/$', csv_download_view, name='csv_download'),
    url(r'^csv/upload/$', csv_upload_view, name='csv_upload'),
    url(r'^csv/inspect/$', csv_inspect_view, name='csv_inspect'),
    ]
