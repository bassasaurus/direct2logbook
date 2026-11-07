"""Owner-only mobile profile; billing and identity fields cannot be changed here."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from home.currency import medical_expiry_date
from profile.models import Profile
from signature.models import Signature
from api.mobile_signature import signature_revision


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ('first_name', 'last_name')


class MedicalSerializer(serializers.ModelSerializer):
    medical_issue_date = serializers.DateField(input_formats=['%Y-%m-%d'], format='%Y-%m-%d')
    class Meta:
        model = Profile
        fields = ('medical_issue_date', 'first_class', 'second_class', 'third_class', 'over_40')

    def validate(self, attrs):
        if sum(bool(attrs.get(key, getattr(self.instance, key)))
               for key in ('first_class', 'second_class', 'third_class')) > 1:
            raise serializers.ValidationError('Select only one medical class.')
        return attrs


def snapshot(user):
    profile = Profile.objects.get(user=user)
    ready = bool(profile.customer_id and profile.subscription_id and profile.end_date)
    if profile.free_access:
        status = 'Free access'
    elif not ready:
        status = 'Setting up'
    elif profile.end_date <= timezone.now().date():
        status = 'Expired'
    elif profile.canceled:
        status = 'Canceled'
    elif profile.trial:
        status = 'Free trial'
    elif profile.trial_expiring:
        status = 'Expiring soon'
    else:
        status = 'Active'
    signature = Signature.objects.filter(user=user).first()
    due_date = medical_expiry_date(profile)
    return {
        'schema_version': 1, 'downloaded_at': timezone.now().isoformat(),
        'account': {**AccountSerializer(user).data, 'username': user.username,
                    'email': user.email, 'joined': user.date_joined.date().isoformat(),
                    'company': profile.company},
        'medical': MedicalSerializer(profile).data,
        'medical_due_date': due_date.isoformat() if due_date else None,
        'subscription': {'status': status, 'end_date': profile.end_date,
                         'plan': 'Monthly' if profile.monthly else 'Yearly' if profile.yearly else None},
        'signature_revision': signature_revision(str(signature.signature) if signature and signature.signature else None),
        'signature': str(signature.signature) if signature and signature.signature else None,
    }


@method_decorator(never_cache, name='dispatch')
class MobileProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(snapshot(request.user))

    @transaction.atomic
    def patch(self, request):
        # Reject unknown fields rather than silently accepting security-sensitive edits.
        if not isinstance(request.data, dict) or set(request.data) - {'account', 'medical'} or not request.data:
            raise serializers.ValidationError('Supply account or medical details only.')
        user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
        profile = Profile.objects.select_for_update().get(user=user)
        if any(value is None for value in request.data.values()):
            raise serializers.ValidationError('Details must be objects, not null.')
        account = request.data.get('account')
        medical = request.data.get('medical')
        account_serializer = medical_serializer = None
        company_serializer = None
        if account is not None:
            if not isinstance(account, dict) or set(account) - {'first_name', 'last_name', 'company'}:
                raise serializers.ValidationError('Only name and company can be updated.')
            account_serializer = AccountSerializer(user, data={k: v for k, v in account.items() if k != 'company'}, partial=True)
            account_serializer.is_valid(raise_exception=True)
            if 'company' in account:
                company_serializer = serializers.CharField(max_length=50, allow_blank=True)
                company = company_serializer.run_validation(account['company'])
        if medical is not None:
            if not isinstance(medical, dict) or set(medical) - set(MedicalSerializer.Meta.fields):
                raise serializers.ValidationError('Unrecognized medical field.')
            medical_serializer = MedicalSerializer(profile, data=medical, partial=True)
            medical_serializer.is_valid(raise_exception=True)
        if account_serializer:
            account_serializer.save()
        if medical_serializer:
            medical_serializer.save()
        if company_serializer:
            profile.company = company
            profile.save(update_fields=['company'])
        return Response(snapshot(user))
