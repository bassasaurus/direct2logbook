# Generated by Django 2.2.4 on 2019-09-18 18:28

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('flights', '0025_importaircraft'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='ImportAircraft',
            new_name='Import',
        ),
    ]
