from django.utils import timezone


def cancellation_scheduled(profile):
    return bool(profile.canceled and profile.active and not profile.expired)


def billing_period_expired(profile):
    # An active subscription still has access on its final billing day. Stripe's
    # ending webhook clears active access when the cancellation takes effect.
    if cancellation_scheduled(profile):
        return False
    return bool(profile.end_date and profile.end_date <= timezone.now().date())
