# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-07-17 17:53
from __future__ import unicode_literals

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0114_auto_20170715_2058'),
    ]

    operations = [
        migrations.AlterField(
            model_name='flight',
            name='duration',
            field=models.FloatField(null=True, validators=[django.core.validators.MinValueValidator(0.1, 'Must be a positive number > 0')]),
        ),
    ]
