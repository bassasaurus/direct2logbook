# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-08-11 17:39
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0128_auto_20170811_1713'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='mapdata',
            name='dst',
        ),
        migrations.RemoveField(
            model_name='mapdata',
            name='timezone_offset',
        ),
    ]
