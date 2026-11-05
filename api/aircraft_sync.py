import hashlib
import json

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from api.models import MobileSyncReceipt
from api.revisions import aircraft_revision
from api.serializers import AircraftSerializer
from flights.models import Aircraft, Flight, Imported, TailNumber


class AircraftOperationSerializer(serializers.Serializer):
    operation_id = serializers.UUIDField()
    action = serializers.ChoiceField(choices=['create', 'update', 'delete'])
    record_id = serializers.IntegerField(min_value=1, required=False)
    base_revision = serializers.CharField(max_length=64, required=False)
    data = serializers.DictField(required=False)

    def validate(self, attrs):
        if attrs['action'] != 'create' and not all(key in attrs for key in ('record_id', 'base_revision')):
            raise serializers.ValidationError('Updates and deletes require a record ID and revision.')
        if attrs['action'] != 'delete' and 'data' not in attrs:
            raise serializers.ValidationError('Aircraft data is required.')
        return attrs


class MobileAircraftSyncView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        operation = AircraftOperationSerializer(data=request.data)
        operation.is_valid(raise_exception=True)
        values = operation.validated_data
        fingerprint = hashlib.sha256(json.dumps({'resource': 'aircraft', **values}, sort_keys=True, default=str).encode()).hexdigest()
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        previous = MobileSyncReceipt.objects.filter(user=request.user, operation_id=values['operation_id']).first()
        if previous:
            if previous.request_hash != fingerprint:
                return Response({'detail': 'Operation ID already used for different data.'}, status=409)
            return Response(previous.response)
        aircraft = None
        if values['action'] != 'create':
            aircraft = Aircraft.objects.select_for_update().filter(pk=values['record_id'], user=request.user).first()
            if aircraft is None:
                return Response({'detail': 'Aircraft no longer available.'}, status=409)
            if aircraft_revision(aircraft) != values['base_revision']:
                return Response({'detail': 'Aircraft changed on the server. Review before syncing.'}, status=409)
        if values['action'] == 'delete':
            # These relationships cascade in the data model. Mobile deletion must
            # never silently remove tailnumbers, flights or imported summaries.
            if (TailNumber.objects.filter(aircraft=aircraft).exists()
                    or Flight.objects.filter(aircraft_type=aircraft).exists()
                    or Imported.objects.filter(aircraft_type=aircraft).exists()):
                return Response({'detail': 'Aircraft is in use by tailnumbers, flights or imported totals and cannot be deleted.'}, status=409)
            record_id = aircraft.pk
            aircraft.delete()
            result = {'operation_id': str(values['operation_id']), 'deleted_id': record_id}
        else:
            data = dict(values['data'])
            for key in ('image', 'id', 'user', 'revision'):
                data.pop(key, None)
            if aircraft and data.get('aircraft_type', aircraft.aircraft_type) != aircraft.aircraft_type:
                return Response({'detail': 'Type designators cannot be renamed through mobile sync. Use the website to rename an existing type.'}, status=400)
            serializer = AircraftSerializer(aircraft, data=data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            aircraft = serializer.save(user=request.user)
            result = {'operation_id': str(values['operation_id']), 'record': AircraftSerializer(aircraft, context={'request': request}).data}
        MobileSyncReceipt.objects.create(user=request.user, operation_id=values['operation_id'], request_hash=fingerprint, response=result)
        return Response(result)
