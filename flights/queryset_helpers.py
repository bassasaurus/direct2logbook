def avoid_none_duration(queryset):

    if not queryset.get('duration__sum'):
        return 0
    else:
        return queryset.get('duration__sum')
