# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-06-10 14:57
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0077_auto_20170610_1455'),
    ]

    operations = [
        migrations.CreateModel(
            name='AircraftCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('aircraft_category', models.CharField(max_length=30)),
            ],
        ),
        migrations.CreateModel(
            name='AircraftClass',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('aircraft_class', models.CharField(max_length=30)),
            ],
        ),
        migrations.RenameField(
            model_name='aircraft',
            old_name='asel',
            new_name='is_default',
        ),
        migrations.AddField(
            model_name='aircraft',
            name='aircraft_category',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='flights.AircraftCategory'),
        ),
        migrations.AddField(
            model_name='aircraft',
            name='aircraft_class',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='flights.AircraftClass'),
        ),
    ]
