# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-08-15 18:07
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0134_aircraft_simple'),
    ]

    operations = [
        migrations.RenameField(
            model_name='flight',
            old_name='aircraft',
            new_name='aircraft_type',
        ),
    ]