from django.contrib.auth.models import User, Group
from rest_framework import serializers
from rest_framework.fields import CharField, SerializerMethodField

from flights.models import Flight, Aircraft, TailNumber, Approach, Holding


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


class ApproachSerializer(serializers.ModelSerializer):
    class Meta:
        model = Approach
        fields = '__all__'


class HoldingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Holding
        fields = '__all__'


class FlightSerializer(serializers.ModelSerializer):

    class Meta:
        model = Flight
        fields = ['id', 'user', 'date', 'aircraft_type', 'registration', 'route', 'duration', 'landings_day', 'landings_night', 
                    'night', 'instrument', 'cross_country', 'second_in_command', 'pilot_in_command', 'simulated_instrument', 
                    'instructor', 'dual', 'remarks', 'solo', 'route_data', 'app_markers', 'app_polylines','approaches']

    aircraft_type = serializers.StringRelatedField()
    registration = serializers.StringRelatedField()
    approaches = SerializerMethodField(source='get_approaches')

    def get_approaches(self, obj):
        approach_queryset = Approach.objects.filter(flight_object=obj.pk)
        return ApproachSerializer(approach_queryset, many=True).data

    def create(self, validated_data):

        validated_data['aircraft_type'] = Aircraft.objects.get(pk=self.initial_data.get('aircraft_type'))
        validated_data['registration'] = TailNumber.objects.get(pk=self.initial_data.get('registration'))
        approaches = self.initial_data.get('approaches')

        flight = Flight.objects.create(**validated_data)

        flight.save()

        for approach in approaches:
            approach['flight_object'] = Flight.objects.get(pk=flight.pk)

            appr_object = Approach.objects.create(**approach)

            appr_object.save()
            
        return Flight.objects.get(pk=flight.pk)


class TailNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = TailNumber
        fields = '__all__'


