# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-11-17 00:22
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0156_remove_flight_geojson'),
    ]

    operations = [
        migrations.AddField(
            model_name='flight',
            name='geojson',
            field=models.TextField(blank=True, null=True),
        ),
    ]