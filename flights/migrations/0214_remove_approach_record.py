# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-09-27 15:25
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0213_approach_record'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='approach',
            name='record',
        ),
    ]
