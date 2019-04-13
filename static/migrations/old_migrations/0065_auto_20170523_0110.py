# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-23 01:10
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0064_remove_stat_aircraft_type'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='stat',
            options={'ordering': ['aircraft_type']},
        ),
        migrations.AlterModelOptions(
            name='total',
            options={},
        ),
        migrations.RemoveField(
            model_name='total',
            name='aircraft_type',
        ),
        migrations.RemoveField(
            model_name='total',
            name='approaches',
        ),
        migrations.AddField(
            model_name='stat',
            name='aircraft_type',
            field=models.CharField(default='', max_length=10),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='stat',
            name='approaches',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='flights.Approach'),
        ),
    ]
