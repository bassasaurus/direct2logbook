from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from flights.airport_resolution import resolve_route, airport_choice_label


def airport_data(airport):
    return {'id': airport.pk, 'label': airport_choice_label(airport), 'icao': airport.icao}


class RouteAirportCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        route = request.query_params.get('route', '')
        if len(route) > 50:
            raise serializers.ValidationError({'route': 'Use 50 characters or fewer.'})
        entries = []
        for item in resolve_route(route):
            entries.append({'position': item['position'], 'code': item['code'],
                            'status': 'unknown' if item['unknown'] else 'ambiguous' if item['needs_confirmation'] else 'recognized',
                            'airport': airport_data(item['airport']) if item['airport'] else None,
                            'candidates': [airport_data(airport) for airport in item['candidates']]})
        response = Response({'entries': entries})
        response['Cache-Control'] = 'no-store'
        return response


def validate_route_choices(route, choices, strict=False):
    if not isinstance(choices, dict):
        raise serializers.ValidationError({'route_airport_choices': 'Invalid airport choices.'})
    selections = choices.get('airports', {}) if choices.get('route') == route else {}
    if not isinstance(selections, dict):
        raise serializers.ValidationError({'route_airport_choices': 'Invalid airport choices.'})
    resolution = resolve_route(route)
    valid = {str(item['position']): {airport.pk for airport in item['candidates']} for item in resolution}
    if any(type(airport_id) is not int or airport_id not in valid.get(position, set())
           for position, airport_id in selections.items()):
        raise serializers.ValidationError({'route_airport_choices': 'An airport choice is no longer valid. Check your route again.'})
    value = {'route': route, 'airports': selections}
    if strict:
        errors = []
        for item in resolve_route(route, value):
            if item['unknown']:
                errors.append(f"{item['code']}: airport not found.")
            elif item['needs_confirmation']:
                errors.append(f"{item['code']}: choose which airport you mean.")
        if errors:
            raise serializers.ValidationError({'route': errors})
    return value
