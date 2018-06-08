from django.conf.urls import url, include

from . import views

urlpatterns = [

    url(r'^pdf_output/$', views.print_view, name='pdf'),

    ]
