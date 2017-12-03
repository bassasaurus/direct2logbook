from django.contrib.auth.models import User, Group
from rest_framework import serializers
from flights.models import *
from flights.fields import *

class UserSerializer(serializers.HyperlinkedModelSerializer):
	class Meta:
		model = User
		fields = ('url', 'username', 'email', 'groups')

class GroupSerializer(serializers.HyperlinkedModelSerializer):
	class Meta:
		model = Group
		fields = ('url', 'name')

class FlightSerializer(serializers.HyperlinkedModelSerializer):
	class Meta:
		model = Flight
		fields = flight_fields()

class AircraftSerializer(serializers.HyperlinkedModelSerializer):
	class Meta:
		model = Aircraft
		fields = aircraft_fields()

class TailNumberSerializer(serializers.HyperlinkedModelSerializer):
	class Meta:
		model = TailNumber
		fields = tailnumber_fields()

class AircraftCategorySerializer(serializers.HyperlinkedModelSerializer):
	class Meta:
		model = AircraftCategory
		fields = '__all__'

class AircraftClassSerializer(serializers.HyperlinkedModelSerializer):
	class Meta:
		model = AircraftClass
		fields = '__all__'

class ApproachSerializer(serializers.HyperlinkedModelSerializer):
	class Meta:
		model = Approach
		fields = '__all__'
