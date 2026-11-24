"""Pilot category/class relationships: 14 CFR 61.5(b), FAA 8710-1 Section III.

Codes are application identifiers. No-class categories store an empty string;
that is different from a missing class in a category with class ratings.
"""
CATEGORY_CHOICES = (
    ('A', 'Airplane'), ('R', 'Rotorcraft'), ('GL', 'Glider'),
    ('PL', 'Powered-Lift'), ('LTA', 'Lighter-Than-Air'),
)
CLASS_CHOICES = (
    ('SEL', 'Single-Engine Land'), ('MEL', 'Multi-Engine Land'),
    ('SES', 'Single-Engine Sea'), ('MES', 'Multi-Engine Sea'),
    ('HELO', 'Helicopter'), ('GYRO', 'Gyroplane'),
    ('BALLOON', 'Balloon'), ('AIRSHIP', 'Airship'),
)
CLASSES_BY_CATEGORY = {
    'A': ('SEL', 'MEL', 'SES', 'MES'), 'R': ('HELO', 'GYRO'),
    'GL': (), 'PL': (), 'LTA': ('BALLOON', 'AIRSHIP'),
}
SUMMARY_CLASSIFICATIONS = {
    'ASEL': ('A', 'SEL'), 'AMEL': ('A', 'MEL'), 'ASES': ('A', 'SES'), 'AMES': ('A', 'MES'),
    'HELO': ('R', 'HELO'), 'GYRO': ('R', 'GYRO'), 'GL': ('GL', ''), 'PL': ('PL', ''),
    'BALLOON': ('LTA', 'BALLOON'), 'AIRSHIP': ('LTA', 'AIRSHIP'),
}


def class_required(category):
    return bool(CLASSES_BY_CATEGORY.get(category))


def class_display(category, aircraft_class):
    if category in CLASSES_BY_CATEGORY and not class_required(category):
        return 'Not applicable'
    return dict(CLASS_CHOICES).get(aircraft_class, 'Not recorded')


def summary_key(category, aircraft_class):
    return next((key for key, pair in SUMMARY_CLASSIFICATIONS.items()
                 if pair == (category, aircraft_class)), None)
