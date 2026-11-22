from django.urls import path
from .views import SignatureCreateView, SignatureDeleteView, SignatureUpdateView

urlpatterns = [
    path('signature/update/', SignatureUpdateView.as_view(), name='signature_update'),

    path('signature_create',
         SignatureCreateView.as_view(), name='signature_create'),
    path('signature_delete/<int:pk>/',
         SignatureDeleteView.as_view(), name='signature_delete'),
]
