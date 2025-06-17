from django.urls import re_path

from .views import PDFView, SignatureCreateView, SignatureUpdateView, SignatureDeleteView

urlpatterns = [

    re_path(r'^pdf_output/(?P<user_id>\d+)/$', PDFView, name='pdf'),

    re_path(r'^pdf_output/signature_create/',
            SignatureCreateView.as_view(), name='signature_create'),
    re_path(r'^pdf_output/signature_update/(?P<pk>\d+)/$',
            SignatureUpdateView.as_view(), name='signature_update'),
    re_path(r'^pdf_output/signature_detail/(?P<pk>\d+)/$',
            SignatureDeleteView.as_view(), name='signature_delete'),

]
