# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-11-17 00:21
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0155_flight_geojson'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='flight',
            name='geojson',
        ),
    ]
