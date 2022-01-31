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
from django.urls import path
from django.contrib import admin
from django.conf.urls.static import static
from django.conf import settings
from errors.views import error_400, error_404, error_500, error_403
from django.urls import path

from rest_framework import routers
from api import views

router = routers.DefaultRouter()
router.register(r'users', views.UserViewSet, basename="User")
# router.register(r'groups', views.GroupViewSet)
router.register(r'flights', views.FlightViewSet, basename='Flight')
router.register(r'aircraft', views.AircraftViewSet, basename='Aircraft')
router.register(r'tailnumbers', views.TailNumberViewSet, basename='TailNumber')

def trigger_error(request):
    division_by_zero = 1 / 0


urlpatterns = [

    path('sentry-debug/', trigger_error),

    path('', include('profile.urls')),
    path('', include('accounts.urls')),
    path('', include('home.urls')),
    path('accounts/', include('allauth.urls')),
    path('admin/', admin.site.urls),
    path('', include('flights.urls')),
    path('', include('pdf_output.urls')),
    path('', include('payments.urls')),
    path('', include('csv_app.urls')),

    path('api/', include(router.urls)),
    path('api/', include('api.urls')),
    path('api/', include('rest_framework.urls', namespace='rest_framework'))
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = error_400
handler403 = error_403
handler404 = error_404
handler500 = error_500


# if settings.DEBUG:
#     import debug_toolbar
#     urlpatterns = [
#         url(r'^__debug__/', include(debug_toolbar.urls)),
#         ] + urlpatterns
