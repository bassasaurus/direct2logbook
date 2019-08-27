from django.db import models
from django.contrib.auth.models import User, Group

from django.dispatch import receiver
from django.db import signals
import datetime
from django.utils import timezone

def user_directory_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'user_{0}/{1}'.format(instance.user.id, filename)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company = models.CharField(max_length=50, default='', blank=True)

    medical_issue_date = models.DateField(default=None, null=True, blank=True)
    first_class = models.BooleanField(default=False)
    second_class = models.BooleanField(default=False)
    third_class = models.BooleanField(default=False)
    over_40 = models.BooleanField(default=False)
    # signature = models.FileField(upload_to=user_directory_path, null=True, blank=True)

    # stripe api response fields
    customer_id = models.CharField(max_length=50, blank=True)
    subscription_id = models.CharField(max_length=50, blank=True)
    active = models.BooleanField(default=False)
    trial = models.BooleanField(default=False)
    trial_expiring = models.BooleanField(default=False)
    today = timezone.now()
    trial_end = models.DateField(default=None, null=True, blank=True)

    def __str__(self):
        title = "{} {}".format(self.user, self.pk)
        return title
