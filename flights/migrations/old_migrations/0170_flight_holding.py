# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-01-17 19:52
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0169_aircraft_light_sport'),
    ]

    operations = [
        migrations.AddField(
            model_name='flight',
            name='holding',
            field=models.NullBooleanField(verbose_name='Holding'),
        ),
    ]
