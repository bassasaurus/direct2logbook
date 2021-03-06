# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-09-06 19:59
from __future__ import unicode_literals

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0203_auto_20180906_1957'),
    ]

    operations = [
        migrations.AlterField(
            model_name='flight',
            name='simulated_instrument',
            field=models.FloatField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0.0, 'Must be a positive number > 0.1')], verbose_name='Sim Inst'),
        ),
    ]
