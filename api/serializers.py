from django.contrib.auth.models import User, Group
from rest_framework import serializers

from flights.models import Flight, Aircraft, TailNumber


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ['url', 'username', 'email']


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ['url', 'name']


class FlightSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Flight
        fields = '__all__'


class AircraftSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Aircraft
        fields = '__all__'


class TailNumberSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = TailNumber
        fields = '__all__'
