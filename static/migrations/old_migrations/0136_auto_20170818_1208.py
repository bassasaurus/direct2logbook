# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-08-18 12:08
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0135_auto_20170815_1807'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aircraft',
            name='aircraft_type',
            field=models.CharField(max_length=10, unique=True),
        ),
    ]
