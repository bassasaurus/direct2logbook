"""Account access shared by sign-in and protected web pages."""
def has_logbook_access(profile):
    return bool(profile and (profile.free_access or profile.trial or
                            (profile.active and not profile.expired)))
