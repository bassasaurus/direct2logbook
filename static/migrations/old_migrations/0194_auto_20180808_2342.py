# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-08-08 23:42
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0193_auto_20180808_2335'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tailnumber',
            name='aircraft_type_error',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='tailnumber',
            name='reg_error',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='tailnumber',
            name='registration_error',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
