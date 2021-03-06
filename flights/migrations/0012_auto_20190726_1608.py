# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2019-07-26 16:08
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('flights', '0011_auto_20190726_1605'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aircraft',
            name='aircraft_type',
            field=models.CharField(db_index=True, max_length=10),
        ),
        migrations.AlterUniqueTogether(
            name='aircraft',
            unique_together=set([('user', 'aircraft_type')]),
        ),
    ]
