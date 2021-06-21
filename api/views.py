from django.contrib.auth.models import User, Group
from rest_framework import viewsets
from rest_framework import permissions
from api.serializers import UserSerializer, GroupSerializer, FlightSerializer, AircraftSerializer, TailNumberSerializer
from flights.models import Flight, Aircraft, TailNumber
from rest_framework.permissions import IsAuthenticated


class UserViewSet(viewsets.ModelViewSet):

    def get_queryset(self):

        user = self.request.user
        return User.objects.filter(pk=user.pk)

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


# class GroupViewSet(viewsets.ModelViewSet):

#     queryset = Group.objects.all()
#     serializer_class = GroupSerializer
#     permission_classes = [permissions.IsAuthenticated]


class FlightViewSet(viewsets.ModelViewSet):

    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        user = self.request.user
        return Flight.objects.filter(user=user)

    serializer_class = FlightSerializer
    # permission_classes = [permissions.IsAuthenticated]


class AircraftViewSet(viewsets.ModelViewSet):

    def get_queryset(self):

        user = self.request.user
        return Aircraft.objects.filter(user=user)

    serializer_class = AircraftSerializer
    permission_classes = [permissions.IsAuthenticated]


class TailNumberViewSet(viewsets.ModelViewSet):

    def get_queryset(self):

        user = self.request.user
        return TailNumber.objects.filter(user=user)

    serializer_class = TailNumberSerializer
    permission_classes = [permissions.IsAuthenticated]
