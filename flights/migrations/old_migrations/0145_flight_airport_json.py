# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-11-06 21:40
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0144_remove_flight_map_feature'),
    ]

    operations = [
        migrations.AddField(
            model_name='flight',
            name='airport_json',
            field=models.TextField(default=''),
        ),
    ]
