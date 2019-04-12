# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-09-06 19:50
from __future__ import unicode_literals

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0200_auto_20180906_1940'),
    ]

    operations = [
        migrations.AlterField(
            model_name='flight',
            name='instrument',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=2, null=True, validators=[django.core.validators.MinValueValidator(0.0, 'Must be a positive number > 0.1')], verbose_name='Inst'),
        ),
        migrations.AlterField(
            model_name='flight',
            name='night',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=2, null=True, validators=[django.core.validators.MinValueValidator(0.0, 'Must be a positive number > 0.1')]),
        ),
    ]