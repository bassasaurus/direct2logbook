# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-01-18 19:01
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AircraftCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ac_category', models.CharField(max_length=30)),
            ],
        ),
        migrations.CreateModel(
            name='AircraftClass',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ac_class', models.CharField(max_length=30)),
            ],
        ),
        migrations.AlterField(
            model_name='aircraft',
            name='ac_category',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='flights.AircraftCategory'),
        ),
        migrations.AlterField(
            model_name='aircraft',
            name='ac_class',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='flights.AircraftClass'),
        ),
        migrations.DeleteModel(
            name='AcCategory',
        ),
        migrations.DeleteModel(
            name='AcClass',
        ),
    ]