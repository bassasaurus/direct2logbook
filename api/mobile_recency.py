"""API representation of the website's currency tables; no device calculations."""
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from home import currency
from flights.models import Total


def landing_status(count, current):
    return {'count': count, 'required': 3, 'current': current}


class MobileRecencyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        categories = []
        flown = set(Total.objects.filter(user=user, total_time__gt=0).values_list('total', flat=True))
        for label, prefix in [('ASEL', 'asel'), ('AMEL', 'amel'), ('ASES', 'ases'),
                              ('AMES', 'ames'), ('HELO', 'helo'), ('GYRO', 'gyro')]:
            if label in flown:
                categories.append({'label': label,
                                   'day': landing_status(*getattr(currency, prefix + '_vfr_day')(user)),
                                   'night': landing_status(*getattr(currency, prefix + '_vfr_night')(user))})
        types = [{'label': label, 'day': landing_status(values[0], values[1]),
                  'night': landing_status(values[2], values[3])}
                 for label, values in sorted(currency.type_currency(user).items())]
        instrument = currency.instrument_recency(user)
        approaches = instrument['appr_quantity']
        return Response({
            'schema_version': 1, 'downloaded_at': timezone.now().isoformat(),
            'as_of': timezone.now().date().isoformat(),
            'categories': categories, 'types': types,
            'instrument': {
                'approaches': {'count': approaches, 'required': 6, 'current': approaches >= 6,
                               'still_needed': max(0, 6 - approaches), 'until': instrument['appr_current_date']},
                'holding': {'count': instrument['hold_quantity'], 'required': 1,
                            'current': bool(instrument['hold_quantity']), 'last_date': instrument['hold_current_date']},
            },
        })
