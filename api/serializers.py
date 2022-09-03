from django.contrib.auth.models import User, Group
from django.core.validators import validate_slug
from rest_framework import serializers
from rest_framework.fields import SerializerMethodField
from collections import OrderedDict

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
                    'instructor', 'simulator', 'dual', 'remarks', 'solo', 'hold', 'app_markers', 'app_polylines','approaches', 'holding']

    aircraft_type = serializers.StringRelatedField()
    registration = serializers.StringRelatedField()
    approaches = SerializerMethodField(source='get_approaches')
    holding = SerializerMethodField(source='get_holding')

    landings_day = serializers.IntegerField(min_value=0, max_value=20, required=False, allow_null=True)
    landings_night = serializers.IntegerField(min_value=0, max_value=20, required=False, allow_null=True)
    instrument = serializers.FloatField(required=False, allow_null=True)
    simulated_instrument = serializers.FloatField(required=False, allow_null=True)


    def to_internal_value(self, data):

        if data.get('landings_day') == '':
            del data['landings_day']

        if data.get('landings_night') == '':
            del data['landings_night']

        if data.get('instrument') == '':
            del data['instrument']

        if data.get('simulated_instrument') == '':
           del data['simulated_instrument']

        if data.get('night') == '':
           del data['night']

        if data.get('holding') == 'false':
            del data['holding']
        
        approach_list = data.get('approaches')

        validated_list = []

        for d in approach_list:
            if d.get('number') == '':
                pass
            else:
                validated_list.append(d)

        data['approaches'] = validated_list

        return super(FlightSerializer, self).to_internal_value(data)


    def get_approaches(self, obj):
        approach_queryset = Approach.objects.filter(flight_object=obj.pk)
        return ApproachSerializer(approach_queryset, many=True).data


    def get_holding(self, obj):
        approach_queryset = Holding.objects.filter(flight_object=obj.pk)
        return HoldingSerializer(approach_queryset, many=True).data


    def create(self, validated_data):

        validated_data['aircraft_type'] = Aircraft.objects.get(user=self.initial_data.get('user'), aircraft_type=self.initial_data.get('aircraft_type'))
        validated_data['registration'] = TailNumber.objects.get(user=self.initial_data.get('user'), registration=self.initial_data.get('registration'))

        approaches = self.initial_data.get('approaches')

        flight = Flight(**validated_data)
        flight.save()

        for approach in approaches:
            approach['flight_object'] = Flight.objects.get(pk=flight.pk)

            appr_object = Approach.objects.create(**approach)

            appr_object.save()
        
        return Flight.objects.get(pk=flight.pk)
        

    def update(self, instance, validated_data):

        validated_data['aircraft_type'] = Aircraft.objects.get(user=self.initial_data.get('user'), aircraft_type=self.initial_data.get('aircraft_type'))
        validated_data['registration'] = TailNumber.objects.get(user=self.initial_data.get('user'), registration=self.initial_data.get('registration'))

        Flight.objects.filter(pk=instance.id).update(**validated_data)
        Flight.objects.get(pk=instance.id).save()

        approaches = self.initial_data.get('approaches')

        for approach in approaches:
            flight = Flight.objects.get(pk=instance.pk)
            if 'id' in approach:
                Approach.objects.filter(id=approach.get('id')).update(**approach)
            else:
                Approach.objects.create(flight_object = flight, approach_type=approach.get('approach_type'), number=approach.get('number'))

        return instance


class TailNumberSerializer(serializers.ModelSerializer):
    aircraft = serializers.StringRelatedField()
    
    class Meta:
        model = TailNumber
        fields = ['id', 'user','registration', 'aircraft', 'is_121', 'is_135', 'is_91']

    

    def create(self, validated_data):

        tailnumber = TailNumber(**validated_data)
        tailnumber.save()

        return TailNumber.objects.get(pk=tailnumber.pk)


