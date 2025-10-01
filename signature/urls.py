from django.urls import path
from .views import SignatureCreateView, SignatureDeleteView

urlpatterns = [

    path('signature_create',
         SignatureCreateView.as_view(), name='signature_create'),
    path('signature_delete/<int:pk>/',
         SignatureDeleteView.as_view(), name='signature_delete'),
]
