# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-17 00:20
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0055_auto_20170516_2350'),
    ]

    operations = [
        migrations.AddField(
            model_name='total',
            name='last_12m',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
        migrations.AddField(
            model_name='total',
            name='last_30',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
        migrations.AddField(
            model_name='total',
            name='last_60',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
        migrations.AddField(
            model_name='total',
            name='last_6m',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
        migrations.AddField(
            model_name='total',
            name='last_90',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
    ]
