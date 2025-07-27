from django.urls import path

from csv_app.views import *

urlpatterns = [
    path('csv/output/', csv_download_view, name='csv_download'),
    path('csv/inspect/', csv_inspect_view, name='csv_inspect'),
    path('csv/upload/', csv_upload_view, name='csv_upload'),
]
