# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-06-10 15:27
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0078_auto_20170610_1457'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='total',
            name='amel',
        ),
    ]
