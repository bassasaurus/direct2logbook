# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-02-06 19:35
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0184_auto_20180206_1922'),
    ]

    operations = [
        migrations.AddField(
            model_name='flight',
            name='crew_error',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]