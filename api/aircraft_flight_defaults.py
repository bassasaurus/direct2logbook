"""Account-owned, revision-checked flight defaults on Aircraft Detail."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication, BasicAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.revisions import aircraft_revision
from api.serializers import AircraftSerializer
from flights.models import Aircraft


class AircraftFlightDefaultsSerializer(serializers.Serializer):
    base_revision = serializers.CharField(max_length=64)
    default_crew_role = serializers.ChoiceField(choices=['', 'PIC', 'SIC'])
    default_cross_country = serializers.BooleanField()


class AircraftFlightDefaultsView(APIView):
    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        serializer = AircraftFlightDefaultsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        aircraft = get_object_or_404(Aircraft.objects.select_for_update(), pk=pk, user=request.user)
        changes = {name: values[name] for name in ('default_crew_role', 'default_cross_country')}
        if aircraft_revision(aircraft) != values['base_revision']:
            # A lost response may safely repeat the same selection.
            if not all(getattr(aircraft, name) == value for name, value in changes.items()):
                return Response({'detail': 'Aircraft changed. Review the defaults and try again.',
                    'record': AircraftSerializer(aircraft, context={'request': request}).data}, status=409)
        else:
            # These preferences never change historical flights or summary totals.
            Aircraft.objects.filter(pk=aircraft.pk).update(**changes)
            for name, value in changes.items():
                setattr(aircraft, name, value)
        return Response({'record': AircraftSerializer(aircraft, context={'request': request}).data})
