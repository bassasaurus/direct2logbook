import hashlib
import json

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import MobileSyncReceipt
from api.revisions import flight_revision
from api.serializers import FlightSerializer
from flights.models import Approach, Flight


class OperationSerializer(serializers.Serializer):
    operation_id = serializers.UUIDField()
    action = serializers.ChoiceField(choices=['create', 'update', 'delete'])
    flight_id = serializers.IntegerField(min_value=1, required=False)
    base_revision = serializers.CharField(max_length=64, required=False)
    data = serializers.DictField(required=False)

    def validate(self, attrs):
        if attrs['action'] != 'create' and not all(key in attrs for key in ('flight_id', 'base_revision')):
            raise serializers.ValidationError('Updates and deletes require a flight ID and base revision.')
        if attrs['action'] != 'delete' and 'data' not in attrs:
            raise serializers.ValidationError('Flight data is required.')
        return attrs


class MobileSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'account_id': request.user.pk, 'sync_protocol': 1, 'aircraft_sync': True, 'route_airport_validation': True})


class MobileFlightSyncView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        operation = OperationSerializer(data=request.data)
        operation.is_valid(raise_exception=True)
        values = operation.validated_data
        fingerprint = hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()
        # Serialize operations per owner, including two concurrent first attempts
        # with the same UUID. Lock the flight too when editing/deleting it.
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        previous = MobileSyncReceipt.objects.filter(
            user=request.user, operation_id=values['operation_id'],
        ).first()
        if previous:
            if previous.request_hash != fingerprint:
                return Response({'code': 'operation_reused', 'detail': 'Operation ID already used with different data.'}, status=409)
            return Response(previous.response)

        flight = None
        if values['action'] != 'create':
            flight = Flight.objects.select_for_update().filter(pk=values['flight_id'], user=request.user).first()
            if flight is None:
                return Response({'code': 'flight_missing', 'detail': 'Flight is no longer available.'}, status=409)
            if flight_revision(flight) != values['base_revision']:
                return Response({'code': 'flight_conflict', 'detail': 'Flight changed on the server.',
                                 'server_flight': FlightSerializer(flight, context={'request': request}).data}, status=409)

        if values['action'] == 'delete':
            flight_id = flight.pk
            flight.delete()
            result = {'operation_id': str(values['operation_id']), 'deleted_id': flight_id}
        else:
            data = dict(values['data'])
            # A full mobile snapshot replaces its approach set, unlike legacy PATCH.
            if isinstance(data.get('approaches'), list):
                data['approaches'] = [
                    {key: value for key, value in row.items() if key not in ('id', 'flight_object')}
                    if isinstance(row, dict) else row for row in data['approaches']
                ]
            serializer = FlightSerializer(flight, data=data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            if flight is not None:
                Approach.objects.filter(flight_object=flight).delete()
            flight = serializer.save(user=request.user)
            result = {'operation_id': str(values['operation_id']),
                      'flight': FlightSerializer(flight, context={'request': request}).data}
        MobileSyncReceipt.objects.create(user=request.user, operation_id=values['operation_id'],
                                         request_hash=fingerprint, response=result)
        return Response(result)
