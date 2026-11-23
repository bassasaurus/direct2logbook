"""Bounded, normalized stroke coordinates shared by web and mobile capture."""
import math
from django.core.exceptions import ValidationError


def validate_strokes(strokes):
    invalid = ValidationError('Draw your signature again. The captured strokes are invalid.')
    if not isinstance(strokes, list) or not 1 <= len(strokes) <= 200:
        raise invalid
    points = []
    for stroke in strokes:
        if not isinstance(stroke, list) or not 1 <= len(stroke) <= 4000:
            raise invalid
        for point in stroke:
            if not isinstance(point, list) or len(point) != 2:
                raise invalid
            if any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) or not 0 <= v <= 1 for v in point):
                raise invalid
            points.append(point)
    if len(points) > 20000:
        raise invalid
    if len(points) < 2 or max(p[0] for p in points) - min(p[0] for p in points) < .01:
        raise ValidationError('Draw your signature before saving.')
