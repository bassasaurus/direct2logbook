"""Logbook choices based on AIM 5-4-5 and 5-4-18.

RNAV entries identify the line of minima; CAT II/III remain explicit ILS
variants. Historical generic choices remain accepted without guessing minima.
"""
APPROACH_CHOICES = (
    ('ILS', 'ILS'), ('CATII', 'ILS CAT II'), ('CATIII', 'ILS CAT III'),
    ('GLS', 'GLS'), ('PAR', 'PAR'),
    ('LNAV', 'RNAV (GPS) — LNAV'), ('LP', 'RNAV (GPS) — LP'),
    ('LNAV/VNAV', 'RNAV (GPS) — LNAV/VNAV'), ('LPV', 'RNAV (GPS) — LPV'),
    ('RNP AR', 'RNAV (RNP) — RNP AR'),
    ('LOC', 'LOC'), ('LOC BC', 'LOC BC'), ('VOR', 'VOR'), ('NDB', 'NDB'),
    ('LDA', 'LDA'), ('LDA/GS', 'LDA with glidepath'), ('SDF', 'SDF'),
    ('TACAN', 'TACAN'), ('ASR', 'ASR'),
)
LEGACY_APPROACH_CHOICES = (
    ('GPS', 'GPS (legacy)'), ('RNAV', 'RNAV (legacy)'), ('MLS', 'MLS (legacy)'),
    ('CAT II', 'ILS CAT II'), ('CAT III', 'ILS CAT III'),
)
ALL_APPROACH_CHOICES = (('', 'Type'),) + APPROACH_CHOICES + LEGACY_APPROACH_CHOICES
