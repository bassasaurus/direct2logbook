# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-07-11 01:10
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0096_stat_last_2yr'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stat',
            name='last_2yr',
            field=models.FloatField(blank=True, null=True, verbose_name='24'),
        ),
    ]
