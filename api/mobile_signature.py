"""Touch-captured account signatures, rendered as PNG for existing web/PDF consumers."""
import base64
import hashlib
from io import BytesIO
from PIL import Image, ImageDraw
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


def signature_revision(value):
    return hashlib.sha256((value or '').encode()).hexdigest()


class SignatureCaptureSerializer(serializers.Serializer):
    revision = serializers.CharField(min_length=64, max_length=64)
    strokes = serializers.ListField(min_length=1, max_length=200,
        child=serializers.ListField(min_length=1, max_length=4000,
            child=serializers.ListField(min_length=2, max_length=2,
                child=serializers.FloatField(min_value=0, max_value=1))))

    def validate_strokes(self, strokes):
        import math
        points = [point for stroke in strokes for point in stroke]
        if len(points) > 20000 or any(not math.isfinite(v) for point in points for v in point):
            raise serializers.ValidationError('Invalid or oversized signature.')
        # A tap alone is not a drawn signature.
        if len(points) < 2 or max(p[0] for p in points) - min(p[0] for p in points) < .01:
            raise serializers.ValidationError('Draw your signature before saving.')
        return strokes


def render_signature(strokes):
    # Supersampling smooths handwriting; retain a fixed 3:1 aspect ratio on all devices.
    image = Image.new('RGBA', (1800, 600), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    for stroke in strokes:
        points = [(round(x * 1799), round(y * 599)) for x, y in stroke]
        if len(points) > 1:
            draw.line(points, fill='black', width=7, joint='curve')
        for x, y in (points[0], points[-1]):
            draw.ellipse((x-3, y-3, x+3, y+3), fill='black')
    image = image.resize((900, 300), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')


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
        current_value = current.signature if current else None
        rendered = render_signature(serializer.validated_data['strokes'])
        # An identical retry after a lost response is safe.
        if serializer.validated_data['revision'] != signature_revision(current_value) and rendered != current_value:
            return Response({'detail': 'Your signature changed on another device. Refresh Profile before replacing it.'},
                            status=status.HTTP_409_CONFLICT)
        field = Signature._meta.get_field('signature')
        try:
            field.clean(rendered, current)
        except ValidationError:
            raise serializers.ValidationError('Signature is too detailed. Clear it and draw again.')
        Signature.objects.update_or_create(user=user, defaults={'signature': rendered})
        from api.mobile_profile import snapshot
        return Response(snapshot(user))
