# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-25 23:49
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0069_auto_20170525_2348'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stat',
            name='_30_days',
            field=models.FloatField(blank=True, null=True, verbose_name='30'),
        ),
    ]