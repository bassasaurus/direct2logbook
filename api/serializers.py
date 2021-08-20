from django.contrib.auth.models import User, Group
from rest_framework import serializers

from flights.models import Flight, Aircraft, TailNumber, Approach


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ['url', 'username', 'email']


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ['url', 'name']


class AircraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aircraft
        fields = '__all__'


class FlightSerializer(serializers.ModelSerializer):

    aircraft_type = serializers.StringRelatedField()
    registration = serializers.StringRelatedField()

    class Meta:
        model = Flight
        fields = '__all__'


class TailNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = TailNumber
        fields = '__all__'