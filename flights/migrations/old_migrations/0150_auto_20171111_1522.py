# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-11-11 15:22
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0149_flight_point_json'),
    ]

    operations = [
        migrations.AlterField(
            model_name='flight',
            name='point_json',
            field=models.TextField(blank=True, null=True),
        ),
    ]
