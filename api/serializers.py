from django.contrib.auth.models import User, Group
from django.db import transaction
from django.core.validators import validate_slug
from rest_framework import serializers
from rest_framework.fields import SerializerMethodField
from collections import OrderedDict

from flights.models import Flight, Aircraft, TailNumber, Approach, Holding

def serializer_owner(serializer):
    request = serializer.context.get('request')
    if request is not None and request.user.is_authenticated:
        return request.user
    if serializer.instance is not None:
        return serializer.instance.user
    raise serializers.ValidationError({'user': 'An authenticated owner is required.'})


def owned_relation(model, owner, value, lookup, field):
    try:
        return model.objects.get(user=owner, **{lookup: value})
    except (model.DoesNotExist, model.MultipleObjectsReturned, TypeError, ValueError):
        raise serializers.ValidationError({
            field: 'Select a valid record belonging to your account.'
        })


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ['url', 'username', 'email']


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ['url', 'name']


class AircraftSerializer(serializers.ModelSerializer):
    # The trusted request owner also feeds per-user uniqueness validation.
    user = serializers.PrimaryKeyRelatedField(
        read_only=True, default=serializers.CurrentUserDefault(),
    )

    class Meta:
        model = Aircraft
        fields = '__all__'
        read_only_fields = ['user']


class ApproachSerializer(serializers.ModelSerializer):
    class Meta:
        model = Approach
        fields = '__all__'


class HoldingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Holding
        fields = '__all__'


class FlightApproachWriteSerializer(serializers.ModelSerializer):
    # Existing IDs must remain available for the ownership check below.
    id = serializers.IntegerField(required=False, min_value=1)
    flight_object = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Approach
        fields = ['id', 'flight_object', 'approach_type', 'number']


class FlightSerializer(serializers.ModelSerializer):

    class Meta:
        model = Flight
        fields = ['id', 'user', 'date', 'aircraft_type', 'registration', 'route', 'duration', 'landings_day', 'landings_night', 
                    'night', 'instrument', 'cross_country', 'second_in_command', 'pilot_in_command', 'simulated_instrument', 
                    'instructor', 'simulator', 'dual', 'remarks', 'solo', 'hold', 'app_markers', 'app_polylines','approaches', 'holding']
        read_only_fields = ['user']

    aircraft_type = serializers.StringRelatedField()
    registration = serializers.StringRelatedField()
    approaches = SerializerMethodField(source='get_approaches')
    holding = SerializerMethodField(source='get_holding')

    landings_day = serializers.IntegerField(min_value=0, max_value=20, required=False, allow_null=True)
    landings_night = serializers.IntegerField(min_value=0, max_value=20, required=False, allow_null=True)
    instrument = serializers.FloatField(required=False, allow_null=True)
    simulated_instrument = serializers.FloatField(required=False, allow_null=True)


    def to_internal_value(self, data):
        data = data.copy()

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
        
        approach_list = data.get('approaches', [])
        if not isinstance(approach_list, list):
            raise serializers.ValidationError({'approaches': 'Expected a list.'})
        # Preserve the existing mobile form convention for empty approach rows.
        rows = [row for row in approach_list
                if not isinstance(row, dict) or row.get('number') != '']
        nested = FlightApproachWriteSerializer(data=rows, many=True)
        if not nested.is_valid():
            raise serializers.ValidationError({'approaches': nested.errors})

        self._validated_approaches = nested.validated_data
        current_flight_id = self.instance.pk if self.instance is not None else None
        for approach in self._validated_approaches:
            if 'flight_object' in approach:
                if approach['flight_object'] != current_flight_id:
                    raise serializers.ValidationError({
                        'approaches': 'Approaches cannot be moved to another flight.'
                    })
                approach.pop('flight_object')
            if 'id' in approach:
                if current_flight_id is None or not Approach.objects.filter(
                    pk=approach['id'], flight_object_id=current_flight_id,
                ).exists():
                    raise serializers.ValidationError({
                        'approaches': 'Approach does not belong to this flight.'
                    })

        return super(FlightSerializer, self).to_internal_value(data)


    def get_approaches(self, obj):
        approach_queryset = Approach.objects.filter(flight_object=obj.pk)
        return ApproachSerializer(approach_queryset, many=True).data


    def get_holding(self, obj):
        approach_queryset = Holding.objects.filter(flight_object=obj.pk)
        return HoldingSerializer(approach_queryset, many=True).data


    def validate(self, attrs):
        attrs = super().validate(attrs)
        owner = serializer_owner(self)
        for field, model, lookup in (
            ('aircraft_type', Aircraft, 'aircraft_type'),
            ('registration', TailNumber, 'registration'),
        ):
            if field in self.initial_data:
                attrs[field] = owned_relation(
                    model, owner, self.initial_data[field], lookup, field,
                )
            elif self.instance is None:
                raise serializers.ValidationError({field: 'This field is required.'})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        flight = Flight.objects.create(**validated_data)
        for approach in self._validated_approaches:
            Approach.objects.create(flight_object=flight, **approach)
        return flight

    @transaction.atomic
    def update(self, instance, validated_data):
        # Recheck ownership under a lock before changing any flight data.
        updates = []
        for approach in self._validated_approaches:
            values = dict(approach)
            approach_id = values.pop('id', None)
            existing = None
            if approach_id is not None:
                existing = Approach.objects.select_for_update().filter(
                    pk=approach_id, flight_object=instance,
                ).first()
                if existing is None:
                    raise serializers.ValidationError({
                        'approaches': 'Approach does not belong to this flight.'
                    })
            updates.append((existing, values))

        instance = super().update(instance, validated_data)
        for existing, values in updates:
            if existing is None:
                Approach.objects.create(flight_object=instance, **values)
            else:
                for name, value in values.items():
                    setattr(existing, name, value)
                existing.save()
        return instance


class TailNumberSerializer(serializers.ModelSerializer):
    # The trusted request owner also feeds per-user uniqueness validation.
    user = serializers.PrimaryKeyRelatedField(
        read_only=True, default=serializers.CurrentUserDefault(),
    )

    aircraft = serializers.StringRelatedField()

    class Meta:
        model = TailNumber
        fields = ['id', 'user', 'registration', 'aircraft', 'is_121', 'is_135', 'is_91']
        read_only_fields = ['user']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if 'aircraft' in self.initial_data:
            value = self.initial_data['aircraft']
            # Keep support for the serializer's PK input and the mobile API's
            # aircraft-type string, without ever using a client-supplied owner.
            lookup = 'pk' if isinstance(value, int) or str(value).isdigit() else 'aircraft_type'
            attrs['aircraft'] = owned_relation(
                Aircraft, serializer_owner(self), value, lookup, 'aircraft',
            )
        elif self.instance is None:
            raise serializers.ValidationError({'aircraft': 'This field is required.'})
        return attrs
