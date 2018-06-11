from django.conf.urls import url, include

from . import views

urlpatterns = [

    url(r'^pdf_output/$', views.PrintView.as_view(), name='pdf'),

    ]
