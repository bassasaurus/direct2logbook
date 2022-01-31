from django.contrib.auth.models import User, Group
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


class FlightViewSet(viewsets.ModelViewSet, CreateModelMixin):

    permission_classes = [IsAuthenticated]
    serializer_class = FlightSerializer

    def get_queryset(self):

        user = self.request.user
        return Flight.objects.filter(user=user)

    def create(self, request, *args, **kwargs):

        request.data['user'] = self.request.user.pk
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def perform_update(self, serializer):
        serializer.save()

    
class AircraftViewSet(viewsets.ModelViewSet):

    def get_queryset(self):

        user = self.request.user
        return Aircraft.objects.filter(user=user)

    serializer_class = AircraftSerializer
    permission_classes = [IsAuthenticated]

    pagination_class = Unpaginated


class TailNumberViewSet(viewsets.ModelViewSet):

    permission_classes = [IsAuthenticated]
    serializer_class = TailNumberSerializer
    pagination_class = Unpaginated

    def get_queryset(self):
        user = self.request.user
        aircraft = self.request.GET['aircraft']
        aircraft_object = Aircraft.objects.get(user=user, aircraft_type=aircraft)
        return TailNumber.objects.filter(user=user, aircraft=aircraft_object)


# @api_view(['GET'])
# @authentication_classes([TokenAuthentication])
# @permission_classes([IsAuthenticated])
# def tailnumber_picker_view(request, aircraft_type):

#     print(request.user)

#     return HttpResponse()

#     # aircraft = Aircraft.objects.get(aircraft_pk)

#     # queryset = TailNumber.objects.filter(user=request.user).filter(aircraft=aircraft).values()

#     # return JsonResponse({"results": list(queryset)})

