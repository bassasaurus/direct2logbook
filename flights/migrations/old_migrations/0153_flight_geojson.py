# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-11-16 01:04
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0152_remove_flight_geojson'),
    ]

    operations = [
        migrations.AddField(
            model_name='flight',
            name='geojson',
            field=models.TextField(blank=True, null=True),
        ),
    ]
