from django.conf.urls import include
from django.urls import re_path
from django.contrib import admin
from django.conf.urls.static import static
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from errors.views import error_400, error_404, error_500, error_403

from rest_framework import routers
from api import views

router = routers.DefaultRouter()
router.register(r'users', views.UserViewSet, basename="User")
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
    path('', include('signature.urls')),

    path('api/', include(router.urls)),
    path('api/', include('api.urls')),
    path('api/', include('rest_framework.urls', namespace='rest_framework')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


handler400 = error_400
handler403 = error_403
handler404 = error_404
handler500 = error_500

# if settings.DEBUG:
#     import debug_toolbar
#     urlpatterns = [
#         path('__debug__/', include(debug_toolbar.urls)),
#     ] + urlpatterns
