# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-10-15 21:08
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0220_auto_20181015_2051'),
    ]

    operations = [
        migrations.RenameField(
            model_name='holding',
            old_name='number',
            new_name='hold_number',
        ),
    ]
