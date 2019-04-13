# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-08-27 17:33
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0139_auto_20170821_0133'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mapdata',
            name='iata',
            field=models.CharField(db_index=True, default='', max_length=3),
        ),
        migrations.AlterField(
            model_name='mapdata',
            name='icao',
            field=models.CharField(db_index=True, default='', max_length=4),
        ),
    ]
