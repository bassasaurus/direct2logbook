from django.conf.urls import url, include

from .views import PDFView, SignatureCreateView, SignatureUpdateView, SignatureDetailView

urlpatterns = [

    url(r'^pdf_output/(?P<user_id>\d+)/$', PDFView, name='pdf'),

    url(r'^pdf_output/signature_create/', SignatureCreateView.as_view(), name='signature_create'),
    url(r'^pdf_output/signature_update/(?P<pk>\d+)/$', SignatureUpdateView.as_view(), name='signature_update'),
    url(r'^pdf_output/signature_detail/(?P<pk>\d+)/$', SignatureDetailView.as_view(), name='signature_detail'),

    ]
