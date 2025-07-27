from django.urls import path
from .views import PDFView, SignatureCreateView, SignatureUpdateView, SignatureDeleteView

urlpatterns = [
    path('pdf_output/<int:user_id>/', PDFView, name='pdf'),
    path('pdf_output/signature_create/',
         SignatureCreateView.as_view(), name='signature_create'),
    path('pdf_output/signature_update/<int:pk>/',
         SignatureUpdateView.as_view(), name='signature_update'),
    path('pdf_output/signature_detail/<int:pk>/',
         SignatureDeleteView.as_view(), name='signature_delete'),
]
