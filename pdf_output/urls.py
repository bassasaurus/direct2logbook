from django.urls import path
from .views import PDFView, pdf_status

urlpatterns = [
    path('pdf_output/status/<uuid:request_id>/', pdf_status, name='pdf_status'),
    path('pdf_output/<int:user_id>/', PDFView, name='pdf'),
]
