"""Touch-captured account signatures, stored as strokes; PNG output preserves existing clients."""
import hashlib
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from signature.models import Signature
from signature.rendering import render_signature
from signature.strokes import validate_strokes


def signature_revision(value):
    return hashlib.sha256((value or '').encode()).hexdigest()


class SignatureCaptureSerializer(serializers.Serializer):
    revision = serializers.CharField(min_length=64, max_length=64)
    strokes = serializers.ListField(min_length=1, max_length=200,
        child=serializers.ListField(min_length=1, max_length=4000,
            child=serializers.ListField(min_length=2, max_length=2,
                child=serializers.FloatField(min_value=0, max_value=1))))

    def validate_strokes(self, strokes):
        try:
            validate_strokes(strokes)
        except ValidationError as error:
            raise serializers.ValidationError(error.messages)
        return strokes


@method_decorator(never_cache, name='dispatch')
class MobileSignatureView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request):
        if not isinstance(request.data, dict) or set(request.data) - {'revision', 'strokes'}:
            raise serializers.ValidationError('Supply revision and strokes only.')
        serializer = SignatureCaptureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Serializes concurrent creates/replacements for this account.
        user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
        current = Signature.objects.filter(user=user).first()
        current_value = current.rendered_signature if current else None
        rendered = render_signature(serializer.validated_data['strokes'])
        # An identical retry after a lost response is safe.
        if serializer.validated_data['revision'] != signature_revision(current_value) and rendered != current_value:
            return Response({'detail': 'Your signature changed on another device. Refresh Profile before replacing it.'},
                            status=status.HTTP_409_CONFLICT)
        saved = current or Signature(user=user)
        saved.set_strokes(serializer.validated_data['strokes'])
        saved.save()
        from api.mobile_profile import snapshot
        return Response(snapshot(user))
