from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from profile.models import Profile


class DistancePreferenceSerializer(serializers.Serializer):
    unit = serializers.ChoiceField(choices=Profile.DistanceUnit.choices)


@method_decorator(never_cache, name='dispatch')
class DistancePreferenceView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'unit': Profile.objects.get(user=request.user).distance_unit})

    def put(self, request):
        form = DistancePreferenceSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        Profile.objects.filter(user=request.user).update(distance_unit=form.validated_data['unit'])
        return Response(form.validated_data)

    def post(self, request):
        self.put(request)
        target = request.data.get('next', '')
        if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            target = reverse('home')
        return HttpResponseRedirect(target)
