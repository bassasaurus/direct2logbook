# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-02-05 23:00
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0178_auto_20180205_2259'),
    ]

    operations = [
        migrations.AddField(
            model_name='aircraft',
            name='power_error',
            field=models.CharField(blank=True, max_length=400, null=True),
        ),
    ]