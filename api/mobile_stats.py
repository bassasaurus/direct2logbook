"""Read-only mobile snapshots of the same summaries displayed on the website."""
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from flights.models import Stat, Total

SUMMARY_FIELDS = (
    'total_time', 'pilot_in_command', 'second_in_command', 'cross_country',
    'instructor', 'dual', 'solo', 'instrument', 'night', 'simulated_instrument',
    'simulator', 'landings_day', 'landings_night', 'last_flown',
    'last_30', 'last_60', 'last_90', 'last_180', 'last_yr', 'last_2yr', 'ytd',
)


class TotalSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Total
        fields = ('total', 'landings_total') + SUMMARY_FIELDS


class AircraftSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Stat
        fields = ('aircraft_type',) + SUMMARY_FIELDS


class MobileStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'schema_version': 1,
            'downloaded_at': timezone.now().isoformat(),
            'totals': TotalSummarySerializer(
                Total.objects.filter(user=request.user).order_by('total', 'pk'), many=True).data,
            'aircraft': AircraftSummarySerializer(
                Stat.objects.filter(user=request.user).order_by('aircraft_type', 'pk'), many=True).data,
        })
