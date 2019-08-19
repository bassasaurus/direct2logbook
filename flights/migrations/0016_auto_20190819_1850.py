# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2019-08-19 18:50
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0015_bulkentry_aircraft_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aircraft',
            name='aircraft_category',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.PROTECT, to='flights.AircraftCategory'),
        ),
        migrations.AlterField(
            model_name='aircraft',
            name='aircraft_class',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.PROTECT, to='flights.AircraftClass'),
        ),
    ]