from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from home.reminder_forms import ReminderForm
from home.medical_reminders import medical_card, medical_preference, medical_generation
from home.currency import medical_expiry_date, instrument_recency, instrument_recency_categories, instrument_currency_notice
from home.reminders import (
    dismiss_medical_warning, dismiss_reminder, medical_expiration_alert, ordered_reminders, reminder_presentation, reminder_rows,
)
from profile.models import Profile, Reminder


@method_decorator(never_cache, name='dispatch')
class MobileRemindersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = get_object_or_404(Profile, user=request.user)
        from home.regulatory_preferences import annotate, notices, snapshot, hidden, key_for
        visible = lambda row: not hidden(profile.web_reminder_preferences.get(key_for(row)), row) if row.get('kind') in ('expiration', 'flight_review', 'instructor_renewal', 'ipc') else True
        return Response({
            'regulatory_alerts': [annotate(profile, row) for row in notices(request.user)],
            'regulatory_preferences': snapshot(profile),
            'medical_card': medical_card(profile),
            'medical_preferences': medical_preference(profile),
            'reminders': [row for row in reminder_rows(request.user) if visible(row)],
            'instrument_alerts': [notice for row in instrument_recency_categories(request.user)
                                  if (notice := instrument_currency_notice(request.user, row)) and visible(notice)],
            'instrument_alert': instrument_currency_notice(request.user, instrument_recency(request.user)),
            'medical_alert': medical_expiration_alert(medical_expiry_date(profile), profile.medical_warning_dismissed_for),
        })


class ReminderDismissSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=48)


@method_decorator(never_cache, name='dispatch')
class MobileMedicalWarningDismissView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReminderDismissSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({'medical_alert': dismiss_medical_warning(request.user, serializer.validated_data['key'])})


@method_decorator(never_cache, name='dispatch')
class MobileReminderDismissView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = ReminderDismissSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dismiss_reminder(request.user, pk, serializer.validated_data['key'])
        return Response({'reminders': reminder_rows(request.user)})


class SavedReminderSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()

    def get_title(self, obj):
        return f"IPC — {obj.get_ipc_category_display() or 'Category not specified'}" if obj.kind == Reminder.Kind.IPC else obj.title

    ipc_completed_date = serializers.DateField(format='%Y-%m-%d')
    instructor_period_start = serializers.DateField(format='%Y-%m-%d')
    last_qualifying_date = serializers.DateField(format='%Y-%m-%d')
    completion_type_label = serializers.SerializerMethodField()
    due_date = serializers.DateField(format='%Y-%m-%d')
    company_start_date = serializers.DateField(format='%Y-%m-%d')
    company_end_date = serializers.DateField(format='%Y-%m-%d')
    target_hours = serializers.DecimalField(max_digits=6, decimal_places=1, coerce_to_string=True)
    dismissed = serializers.SerializerMethodField()
    goal_label = serializers.SerializerMethodField()
    progress_label = serializers.SerializerMethodField()
    status_message = serializers.SerializerMethodField()
    holding_warning = serializers.SerializerMethodField()
    milestone_state = serializers.SerializerMethodField()
    banner = serializers.SerializerMethodField()
    severity = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    completion_percent = serializers.SerializerMethodField()
    hours_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Reminder
        fields = ('id', 'title', 'kind', 'due_date', 'target_hours', 'aircraft', 'crew_position',
                  'company', 'company_start_date', 'company_end_date', 'goal_label', 'progress_label', 'status_message', 'holding_warning', 'dismissed', 'milestone_state', 'banner', 'severity', 'days_remaining', 'completion_percent', 'hours_remaining', 'last_qualifying_date', 'completion_type', 'completion_type_label', 'condition', 'instructor_period_start', 'ipc_completed_date', 'ipc_category')

    def to_representation(self, instance):
        if instance.kind == Reminder.Kind.IPC:
            from home.currency import instrument_recency
            instance.due_date = instrument_recency(instance.user_id, ipc=instance)['instrument_review_date']
        return super().to_representation(instance)

    def get_completion_type_label(self, obj):
        return obj.get_completion_type_display() if obj.kind == Reminder.Kind.FLIGHT_REVIEW else None

    def get_dismissed(self, obj):
        return bool(obj.dismissed_key)

    def get_goal_label(self, obj):
        return obj.milestone_label() if not obj.is_dated else None

    def presentation(self, obj):
        if not hasattr(self, '_presentations'):
            self._presentations = {}
        if obj.pk not in self._presentations:
            self._presentations[obj.pk] = reminder_presentation(obj)
        return self._presentations[obj.pk]

    def get_holding_warning(self, obj):
        return self.presentation(obj).get('holding_warning')

    def get_status_message(self, obj):
        return self.presentation(obj).get('status_message')

    def get_progress_label(self, obj):
        return self.presentation(obj)['progress_label']

    def get_milestone_state(self, obj):
        return self.presentation(obj)['milestone_state']

    def get_banner(self, obj):
        return self.presentation(obj)['banner']

    def get_severity(self, obj):
        return self.presentation(obj)['severity']

    def get_days_remaining(self, obj):
        return self.presentation(obj)['days_remaining']

    def get_completion_percent(self, obj):
        return self.presentation(obj)['completion_percent']

    def get_hours_remaining(self, obj):
        return self.presentation(obj)['hours_remaining']


@transaction.atomic
def save_reminder(request, instance=None):
    if not isinstance(request.data, dict):
        raise serializers.ValidationError('Expected a reminder object.')
    for field in ('title', 'kind', 'due_date', 'crew_position', 'company', 'company_start_date', 'company_end_date', 'last_qualifying_date', 'completion_type', 'condition', 'instructor_period_start', 'ipc_completed_date', 'ipc_category'):
        value = request.data.get(field)
        if value is not None and not isinstance(value, str):
            raise serializers.ValidationError({field: ['Expected a string.']})
    aircraft = request.data.get('aircraft')
    if aircraft is not None and (type(aircraft) is not int or aircraft <= 0):
        raise serializers.ValidationError({'aircraft': ['Choose an aircraft type.']})
    form = ReminderForm(request.data, instance=instance, user=request.user)
    if not form.is_valid():
        raise serializers.ValidationError(dict(form.errors))
    return SavedReminderSerializer(form.save_for_user(request.user)).data


@method_decorator(never_cache, name='dispatch')
class MobileSavedRemindersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reminders = Reminder.objects.filter(user=request.user).select_related('aircraft').order_by('pk')
        return Response({'reminders': ordered_reminders(SavedReminderSerializer(reminders, many=True).data)})

    def post(self, request):
        return Response(save_reminder(request), status=status.HTTP_201_CREATED)


@method_decorator(never_cache, name='dispatch')
class MobileSavedReminderView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request, pk):
        Profile.objects.select_for_update().get(user=request.user)
        reminder = get_object_or_404(Reminder.objects.select_for_update(), user=request.user, pk=pk)
        return Response(save_reminder(request, instance=reminder))

    def delete(self, request, pk):
        from home.reminder_removal import remove_saved_reminder
        remove_saved_reminder(request.user, pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(never_cache, name='dispatch')
class MobileReminderRestoreView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        reminder = get_object_or_404(Reminder, user=request.user, pk=pk)
        Reminder.objects.filter(user=request.user, pk=reminder.pk).update(dismissed_key='')
        reminder.dismissed_key = ''
        return Response(SavedReminderSerializer(reminder).data)


class MedicalPreferenceSerializer(serializers.Serializer):
    generation = serializers.IntegerField(min_value=0, default=0)
    caution_due = serializers.DateField(required=False, allow_null=True, input_formats=['%Y-%m-%d'], format='%Y-%m-%d')
    until = serializers.DateField(required=False, allow_null=True, input_formats=['%Y-%m-%d'], format='%Y-%m-%d')


@method_decorator(never_cache, name='dispatch')
class MobileMedicalPreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = get_object_or_404(Profile, user=request.user)
        return Response({'preference': medical_preference(profile), 'generation': medical_generation(profile)})

    @transaction.atomic
    def put(self, request):
        from datetime import timedelta, timezone as utc_timezone
        from django.utils import timezone
        from home.medical_reminders import clear_medical_preferences
        if not isinstance(request.data, dict) or set(request.data) - {'caution_due', 'until', 'generation'}:
            raise serializers.ValidationError('Supply a medical dismissal or snooze date.')
        serializer = MedicalPreferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = Profile.objects.select_for_update().get(user=request.user)
        if serializer.validated_data['generation'] != medical_generation(profile):
            return Response({'preference': medical_preference(profile), 'generation': medical_generation(profile)})
        due = medical_expiry_date(profile)
        alert = medical_expiration_alert(due)
        today = timezone.localdate(timezone=utc_timezone.utc)
        values = serializer.validated_data
        until, caution = values.get('until'), values.get('caution_due')
        if until and until > today + timedelta(days=30):
            raise serializers.ValidationError({'until': 'Snooze for at most 30 days.'})
        preference = {'title': 'Medical Certificate'}
        if until and until > today:
            preference['until'] = until.isoformat()
        elif caution and caution == due and alert['severity'] == 'warning':
            preference['caution_due'] = caution.isoformat()
        if len(preference) == 1:
            clear_medical_preferences(profile, invalidate=False)
        else:
            profile.web_reminder_preferences = {**profile.web_reminder_preferences, 'medical': preference}
            profile.medical_warning_dismissed_for = None
            profile.save(update_fields=['web_reminder_preferences', 'medical_warning_dismissed_for'])
        return Response({'preference': medical_preference(profile), 'generation': medical_generation(profile)})


@method_decorator(never_cache, name='dispatch')
class MobileRegulatoryPreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from home.regulatory_preferences import snapshot
        return Response(snapshot(get_object_or_404(Profile, user=request.user)))

    def post(self, request):
        from datetime import date
        from home.regulatory_preferences import apply_action
        data = request.data
        if not isinstance(data, dict) or set(data) - {'key', 'action', 'generation', 'due', 'severity', 'until'}:
            raise serializers.ValidationError('Choose a reminder action.')
        if not isinstance(data.get('key'), str) or not data['key'].startswith(('regulatory:', 'ifr:')):
            raise serializers.ValidationError('Choose a regulatory reminder.')
        if data.get('action') not in ('snooze', 'dismiss', 'restore') or type(data.get('generation')) is not int:
            raise serializers.ValidationError('Choose a valid reminder action.')
        try:
            until = date.fromisoformat(data['until']) if data.get('until') else None
            return Response(apply_action(request.user, data['key'], data['action'], data['generation'],
                data.get('due'), data.get('severity'), until))
        except (TypeError, ValueError):
            raise serializers.ValidationError('Choose a valid reminder return date.')
