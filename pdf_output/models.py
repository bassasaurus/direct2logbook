from django.db import models
from django.contrib.auth.models import User

# Create your models here.


def user_directory_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'user_{0}/{1}'.format(instance.user.id, filename)


class Signature(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    signature = models.ImageField(upload_to=user_directory_path)
