def flight_fields():
	return [
			'date',
			'aircraft_type',
			'registration',
			'route',
			'legs',
			'duration',
			'landings_day',
			'landings_night',
			'night',
			'instrument',
			'approaches',
			'holding',
			'cross_country',
			'second_in_command',
			'pilot_in_command',
			'simulated_instrument',
			'instructor',
			'dual',
			'remarks',
			'simulator',
			'solo',
			]


def aircraft_fields():
	return [
			'aircraft_type',
			'turbine',
			'piston',
			'requires_type',
			'superr',
			'heavy',
			'large',
			'medium',
			'small',
			'tailwheel',
			'simple',
			'compleks',
			'high_performance',
			'light_sport',
			'aircraft_category',
			'aircraft_class',
			'image',
			]


def approach_fields():
	return [
			'approach_type',
			'number',
			]


def tailnumber_fields():
	return[
			'registration',
			'aircraft',
			'is_121',
			'is_135',
			'is_91',
			]
