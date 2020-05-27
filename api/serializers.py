from django.contrib.auth.models import User, Group
from django.contrib.auth import get_user_model
from rest_framework import serializers
from flights.models import Flight, Aircraft, TailNumber


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ('url', 'username', 'email', 'groups')


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
