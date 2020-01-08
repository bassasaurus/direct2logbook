from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
# Create your models here.


def user_directory_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'app/user_{0}/{1}'.format(instance.user.id, filename)


class Signature(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    signature = models.ImageField(upload_to=user_directory_path)

    class Meta:
        ordering = ['-created_at', 'user']
        get_latest_by = ['signature']
