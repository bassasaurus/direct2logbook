"""Account-scoped default aircraft preference, using the mobile receipt protocol."""
import hashlib
import json
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from api.models import MobileSyncReceipt
from flights.models import Aircraft


def default_aircraft_record(user):
    aircraft = Aircraft.objects.filter(user=user, is_default=True).first()
    code = aircraft.aircraft_type if aircraft else ''
    revision = hashlib.sha256(json.dumps([aircraft.pk if aircraft else None, code]).encode()).hexdigest()
    return {'id': -1, 'aircraft_type': code, 'revision': revision, '_default_preference': True}


class DefaultOperation(serializers.Serializer):
    operation_id = serializers.UUIDField()
    action = serializers.ChoiceField(choices=['create', 'update'])
    base_revision = serializers.CharField(max_length=64, required=False)
    data = serializers.DictField()

    def validate(self, attrs):
        if attrs['action'] == 'update' and not attrs.get('base_revision'):
            raise serializers.ValidationError('A default preference revision is required.')
        code = attrs['data'].get('aircraft_type')
        if not isinstance(code, str) or len(code) > 10:
            raise serializers.ValidationError('Choose an aircraft type or clear the selection.')
        return attrs


class MobileDefaultAircraftView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(default_aircraft_record(request.user))

    @transaction.atomic
    def post(self, request):
        operation = DefaultOperation(data=request.data)
        operation.is_valid(raise_exception=True)
        values = operation.validated_data
        fingerprint = hashlib.sha256(json.dumps({'resource': 'default-aircraft', **values}, sort_keys=True, default=str).encode()).hexdigest()
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        previous = MobileSyncReceipt.objects.filter(user=request.user, operation_id=values['operation_id']).first()
        if previous:
            if previous.request_hash != fingerprint:
                return Response({'detail': 'Operation ID already used for different data.'}, status=409)
            return Response(previous.response)
        current = default_aircraft_record(request.user)
        if ((values['action'] == 'update' and values['base_revision'] != current['revision'])
                or (values['action'] == 'create' and current['aircraft_type'])):
            return Response({'detail': 'Default aircraft changed on the server. Review before syncing.'}, status=409)
        code = values['data']['aircraft_type']
        aircraft = Aircraft.objects.filter(user=request.user, aircraft_type=code).first() if code else None
        if code and not aircraft:
            raise serializers.ValidationError({'aircraft_type': 'Choose an aircraft belonging to your account.'})
        Aircraft.objects.filter(user=request.user, is_default=True).update(is_default=False)
        if aircraft:
            Aircraft.objects.filter(pk=aircraft.pk, user=request.user).update(is_default=True)
        result = {'operation_id': str(values['operation_id']), 'record': default_aircraft_record(request.user)}
        MobileSyncReceipt.objects.create(user=request.user, operation_id=values['operation_id'], request_hash=fingerprint, response=result)
        return Response(result)
