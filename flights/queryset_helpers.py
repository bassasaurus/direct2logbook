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


def is_user_deletion(origin):
    """Do not rebuild summaries already included in a user deletion cascade."""
    from django.contrib.auth import get_user_model
    return origin is not None and (getattr(origin, 'model', None) or type(origin)) is get_user_model()
