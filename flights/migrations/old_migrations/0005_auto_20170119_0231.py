# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-01-19 02:31
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0004_auto_20170118_1913'),
    ]

    operations = [
        migrations.RenameField(
            model_name='aircraftcategory',
            old_name='ac_category',
            new_name='aircraft_category',
        ),
        migrations.RenameField(
            model_name='aircraftclass',
            old_name='ac_class',
            new_name='aircraft_class',
        ),
    ]
