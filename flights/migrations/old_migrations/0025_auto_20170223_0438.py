# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-23 04:38
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0024_auto_20170223_0432'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aircraft',
            name='aircraft_type',
            field=models.CharField(max_length=10),
        ),
        migrations.AlterField(
            model_name='tailnumber',
            name='registration',
            field=models.CharField(max_length=10),
        ),
    ]