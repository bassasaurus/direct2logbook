# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-02-05 22:59
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0177_auto_20180204_2251'),
    ]

    operations = [
        migrations.RenameField(
            model_name='aircraft',
            old_name='error',
            new_name='configuration_error',
        ),
    ]
