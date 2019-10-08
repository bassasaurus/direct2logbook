from django.db.models import Sum


def avoid_none(queryset, field):

    field__sum = str(field + '__sum')

    queryset = queryset.aggregate(Sum(field))

    if not queryset.get(field__sum):
        return 0
    else:
        return round(queryset.get(field__sum), 1)


def zero_if_none(object):
    if not object:
        return 0
    else:
        return object
