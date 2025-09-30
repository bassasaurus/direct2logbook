from django.urls import path
from .views import PDFView

urlpatterns = [
    path('pdf_output/<int:user_id>/', PDFView, name='pdf'),
]
