from django.urls import path, re_path

from csv_app.views import *

urlpatterns = [

    path(r'^csv/output/$', csv_download_view, name='csv_download'),
    path(r'^csv/inspect/$', csv_inspect_view, name='csv_inspect'),
    path(r'^csv/upload/$', csv_upload_view, name='csv_upload'),
]
