# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-08-09 00:17
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0196_auto_20180809_0015'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tailnumber',
            name='aircraft_type_error',
        ),
    ]
