from django.db.models import Sum
from decimal import *


getcontext().prec = 1


def avoid_none(queryset: object, field: object) -> object:

    field__sum = str(field + '__sum')

    queryset = queryset.aggregate(Sum(field))

    if not queryset.get(field__sum):
        return Decimal(0)
    else:
        return Decimal(queryset.get(field__sum))


def zero_if_none(object):
    if not object:
        return 0
    else:
        return object
