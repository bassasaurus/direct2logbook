# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-10-05 17:27
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0214_remove_approach_record'),
    ]

    operations = [
        migrations.AddField(
            model_name='approach',
            name='flight_object',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, to='flights.Flight', verbose_name='Flight'),
        ),
        migrations.AlterField(
            model_name='approach',
            name='approach_type',
            field=models.CharField(max_length=15, verbose_name='Approach Type'),
        ),
        migrations.AlterField(
            model_name='approach',
            name='number',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Number'),
        ),
    ]
