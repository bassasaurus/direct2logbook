# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-22 01:38
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0063_remove_stat_approaches'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='stat',
            name='aircraft_type',
        ),
    ]
