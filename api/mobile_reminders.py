from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from home.reminder_forms import ReminderForm
from home.currency import medical_expiry_date
from home.reminders import (
    dismiss_medical_warning, dismiss_reminder, medical_expiration_alert, milestone_progress_label, reminder_rows,
)
from profile.models import Profile, Reminder


@method_decorator(never_cache, name='dispatch')
class MobileRemindersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = get_object_or_404(Profile, user=request.user)
        return Response({
            'reminders': reminder_rows(request.user),
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
    due_date = serializers.DateField(format='%Y-%m-%d')
    company_start_date = serializers.DateField(format='%Y-%m-%d')
    company_end_date = serializers.DateField(format='%Y-%m-%d')
    target_hours = serializers.DecimalField(max_digits=6, decimal_places=1, coerce_to_string=True)
    goal_label = serializers.SerializerMethodField()
    progress_label = serializers.SerializerMethodField()

    class Meta:
        model = Reminder
        fields = ('id', 'title', 'kind', 'due_date', 'target_hours', 'aircraft', 'crew_position',
                  'company', 'company_start_date', 'company_end_date', 'goal_label', 'progress_label')

    def get_goal_label(self, obj):
        return obj.milestone_label() if obj.kind != Reminder.Kind.EXPIRATION else None

    def get_progress_label(self, obj):
        return milestone_progress_label(obj)


def save_reminder(request, instance=None):
    if not isinstance(request.data, dict):
        raise serializers.ValidationError('Expected a reminder object.')
    for field in ('title', 'kind', 'due_date', 'crew_position', 'company', 'company_start_date', 'company_end_date'):
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
        return Response({'reminders': SavedReminderSerializer(reminders, many=True).data})

    def post(self, request):
        return Response(save_reminder(request), status=status.HTTP_201_CREATED)


@method_decorator(never_cache, name='dispatch')
class MobileSavedReminderView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request, pk):
        reminder = get_object_or_404(Reminder.objects.select_for_update(), user=request.user, pk=pk)
        return Response(save_reminder(request, instance=reminder))

    def delete(self, request, pk):
        get_object_or_404(Reminder, user=request.user, pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
