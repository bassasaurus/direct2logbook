# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-06-01 14:19
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0073_auto_20170601_1418'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stat',
            name='ydt',
            field=models.FloatField(blank=True, null=True, verbose_name='ydt'),
        ),
    ]
