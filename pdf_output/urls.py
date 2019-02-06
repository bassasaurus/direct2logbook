from django.conf.urls import url, include

from pdf_output.views import *

urlpatterns = [

    url(r'^pdf_output/(?P<user_id>\d+)/$', PDFView, name='pdf'),
    # url(r'^log_table/$', PDFView.as_view(), name='log_table'),
    ]
