def flight_fields():
	return [
			'date',
			'aircraft_type',
			'registration',
			'route',
			'duration',
			'landings_day',
			'landings_night',
			'night',
			'instrument',
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


def tailnumber_fields():
	return[
			'registration',
			'aircraft',
			'is_121',
			'is_135',
			'is_91',
			]

def bulk_entry_fields():
	return[
			'aircraft_type',
			'aircraft_category',
			'aircraft_class',
			'total_time',
			'pilot_in_command',
			'second_in_command',
			'cross_country',
			'instructor',
			'dual',
			'solo',
			'instrument',
			'night',
			'simulated_instrument',
			'simulator',
			'landings_day',
			'landings_night',
			'landings_total',
			'last_flown',
			'last_30',
			'last_60',
			'last_90',
			'last_180',
			'last_yr',
			'last_2yr',
			'ytd'
	]
