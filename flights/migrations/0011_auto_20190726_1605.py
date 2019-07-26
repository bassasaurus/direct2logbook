# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2019-07-26 16:05
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('flights', '0010_remove_bulkentry_registration'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tailnumber',
            name='registration',
            field=models.CharField(db_index=True, max_length=10),
        ),
        migrations.AlterUniqueTogether(
            name='tailnumber',
            unique_together=set([('user', 'registration')]),
        ),
    ]
