from django.conf.urls import url, include

from pdf_output.views import *

urlpatterns = [

    url(r'^pdf_output/$', PDFView.as_view(), name='pdf'),
    url(r'^log_table/$', LogView.as_view(), name='log_table'),
    ]
