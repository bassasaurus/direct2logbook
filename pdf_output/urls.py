from django.conf.urls import url, include

from .views import PDFView, SignatureCreate, SignatureUpdate

urlpatterns = [

    url(r'^pdf_output/(?P<user_id>\d+)/$', PDFView, name='pdf'),

    url(r'^pdf_output/signature_create/', SignatureCreate.as_view(), name='signature_create'),
    url(r'^pdf_output/signature_update/(?P<pk>\d+)/$', SignatureUpdate.as_view(), name='signature_update'),
    ]
