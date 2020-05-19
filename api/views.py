from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.reverse import reverse
from rest_framework import generics
from flights.models import Flight, Aircraft, TailNumber
import api.serializers as serializers
from .serializers import UserSerializer


from django.contrib.auth.models import User, Group
from rest_framework import viewsets


class FlightViewSet(viewsets.ModelViewSet):
    queryset = Flight.objects.all()
    serializer_class = serializers.FlightSerializer


class AircraftViewSet(viewsets.ModelViewSet):
    queryset = Aircraft.objects.all()
    serializer_class = serializers.AircraftSerializer


class TailNumberViewSet(viewsets.ModelViewSet):
    queryset = TailNumber.objects.all()
    serializer_class = serializers.TailNumberSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
