# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-08-08 23:50
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0194_auto_20180808_2342'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tailnumber',
            name='registration_error',
        ),
    ]
