# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2019-04-01 19:46
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0228_auto_20190315_1454'),
    ]

    operations = [
        migrations.RenameField(
            model_name='profile',
            old_name='log_table',
            new_name='signature',
        ),
    ]
