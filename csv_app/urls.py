from django.urls import path

from csv_app.views import *

urlpatterns = [
    path('csv/inspect/<uuid:batch_id>/preview/', csv_preview_view, name='csv_preview'),
    path('csv/inspect/<uuid:batch_id>/overlaps/', csv_overlaps_view, name='csv_overlaps'),
    path('csv/inspect/<uuid:batch_id>/rows/', csv_rows_view, name='csv_rows'),
    path('csv/inspect/<uuid:batch_id>/records/', csv_records_view, name='csv_records'),
    path('csv/inspect/<uuid:batch_id>/records/new/<str:kind>/<int:index>/', csv_create_record_view, name='csv_create_record'),
    path('csv/inspect/<uuid:batch_id>/columns/', csv_mapping_view, name='csv_mapping'),
    path('csv/inspect/<uuid:batch_id>/dates/', csv_date_order_view, name='csv_date_order'),
    path('csv/template/', csv_template_view, name='csv_template'),
    path('csv/import/status/<uuid:batch_id>/', csv_import_status, name='csv_import_status'),
    path('csv/output/', csv_download_view, name='csv_download'),
    path('csv/inspect/', csv_inspect_view, name='csv_inspect'),
    path('csv/upload/', csv_upload_view, name='csv_upload'),
]
