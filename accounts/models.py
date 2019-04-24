from django.db import models
from django.contrib.auth.models import User, Group

from django.dispatch import receiver
from django.db import signals

# def user_directory_path(instance, filename):
#     # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
#     return 'user_{0}/{1}'.format(instance.user.id, filename)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company = models.CharField(max_length=50, default='')
    signature = models.FileField(upload_to=user_directory_path)

    def __str__(self):
        title = "{} {}".format(self.user, self.pk)
        return title
