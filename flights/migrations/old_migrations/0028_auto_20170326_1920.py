# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-26 19:20
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0027_remove_flight_dummy_reg'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='aircraft',
            options={'ordering': ['-aircraft_type']},
        ),
        migrations.AlterModelOptions(
            name='tailnumber',
            options={'ordering': ['-aircraft']},
        ),
    ]