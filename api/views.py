from django.contrib.auth.models import User, Group
from django.db.models.functions import Lower
from api.ordering import natural_registration_order
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework import permissions
from rest_framework.response import Response
from api.serializers import UserSerializer, GroupSerializer, FlightSerializer, AircraftSerializer, TailNumberSerializer
from flights.models import Flight, Aircraft, TailNumber
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes, api_view, authentication_classes
from rest_framework.authentication import BasicAuthentication, TokenAuthentication
from django.http import HttpResponse, JsonResponse
from rest_framework.mixins import CreateModelMixin

from rest_framework.pagination import LimitOffsetPagination


class Unpaginated(LimitOffsetPagination):

    def paginate_queryset(self, queryset, request, view=None):
        self.count = self.get_count(queryset)
        self.limit = self.get_limit(request)
        self.offset = self.get_offset(request)
        self.request = request
        self.display_page_controls = False

        return list(queryset)


class UserViewSet(viewsets.ModelViewSet):

    def get_queryset(self):

        user = self.request.user
        return User.objects.filter(pk=user.pk)

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]


# class GroupViewSet(viewsets.ModelViewSet):

#     queryset = Group.objects.all()
#     serializer_class = GroupSerializer
#     permission_classes = [permissions.IsAuthenticated]


class OwnedRecordsViewSet(viewsets.ModelViewSet):
    """Only the server chooses ownership, on both creation and update."""
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)


class FlightViewSet(OwnedRecordsViewSet):
    serializer_class = FlightSerializer

    def get_queryset(self):

        user = self.request.user
        return Flight.objects.filter(user=user)


class AircraftViewSet(OwnedRecordsViewSet):

    def get_queryset(self):

        user = self.request.user
        return Aircraft.objects.filter(user=user).order_by(Lower('aircraft_type'), 'pk')

    serializer_class = AircraftSerializer
    permission_classes = [IsAuthenticated]

    pagination_class = Unpaginated


class TailNumberViewSet(OwnedRecordsViewSet):

    permission_classes = [IsAuthenticated]
    serializer_class = TailNumberSerializer
    pagination_class = Unpaginated

    def get_queryset(self):
        user = self.request.user
        return natural_registration_order(TailNumber.objects.filter(user=user))
