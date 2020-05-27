"""logbook URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from django.conf.urls.static import static
from django.conf import settings
from django.conf.urls import handler404, handler500, handler403
from flights.views import error_400, error_404, error_500, error_403

from django.urls import path

def trigger_error(request):
    division_by_zero = 1 / 0



urlpatterns = [

    path('sentry-debug/', trigger_error),

    url(r'^', include('profile.urls')),
    url(r'^', include('accounts.urls')),
    url(r'^', include('home.urls')),
    url(r'^accounts/', include('allauth.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^', include('flights.urls')),
    url(r'^', include('pdf_output.urls')),
    url(r'^', include('payments.urls')),
    url(r'^', include('csv_app.urls')),
    url(r'^api/', include('api.urls')),
    # url(r'^api/docs/', include('rest_framework_docs.urls')),
    ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = error_400
handler403 = error_403
handler404 = error_404
handler500 = error_500

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
