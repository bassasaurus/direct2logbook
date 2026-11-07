import hashlib
import json
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from api.models import MobileSyncReceipt
from api.serializers import TailNumberSerializer


class TailnumberOperationSerializer(serializers.Serializer):
    operation_id = serializers.UUIDField()
    action = serializers.ChoiceField(choices=['create'])
    data = serializers.DictField()


class MobileTailnumberSyncView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        operation = TailnumberOperationSerializer(data=request.data)
        operation.is_valid(raise_exception=True)
        values = operation.validated_data
        fingerprint = hashlib.sha256(json.dumps({'resource': 'tailnumber', **values}, sort_keys=True, default=str).encode()).hexdigest()
        # Use the same per-account lock as aircraft/flight sync and durable
        # receipts: retries after a lost response must never create a second row.
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        previous = MobileSyncReceipt.objects.filter(user=request.user, operation_id=values['operation_id']).first()
        if previous:
            if previous.request_hash != fingerprint:
                return Response({'detail': 'Operation ID already used for different data.'}, status=409)
            return Response(previous.response)
        data = {key: value for key, value in values['data'].items()
                if key in ('registration', 'aircraft', 'is_91', 'is_135', 'is_121')}
        registration = data.get('registration')
        if not isinstance(registration, str):
            raise serializers.ValidationError({'registration': 'Registration is required.'})
        data['registration'] = registration.strip().upper().replace(' ', '')
        serializer = TailNumberSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        tail = serializer.save(user=request.user)
        result = {'operation_id': str(values['operation_id']), 'record': TailNumberSerializer(tail, context={'request': request}).data}
        MobileSyncReceipt.objects.create(user=request.user, operation_id=values['operation_id'], request_hash=fingerprint, response=result)
        return Response(result)
