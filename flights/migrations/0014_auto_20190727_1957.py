# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2019-07-27 19:57
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0013_remove_bulkentry_aircraft_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='bulkentry',
            name='aircraft_category',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='flights.AircraftCategory'),
        ),
        migrations.AddField(
            model_name='bulkentry',
            name='aircraft_class',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='flights.AircraftClass'),
        ),
    ]