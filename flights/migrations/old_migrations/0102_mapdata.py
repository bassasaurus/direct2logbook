# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-07-12 10:45
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0101_auto_20170711_0133'),
    ]

    operations = [
        migrations.CreateModel(
            name='MapData',
            fields=[
                ('airport_id', models.PositiveIntegerField(primary_key=True, serialize=False)),
                ('name', models.CharField(default='', max_length=50)),
                ('city', models.CharField(default='', max_length=50)),
                ('country', models.CharField(default='', max_length=50)),
                ('iata', models.CharField(default='', max_length=3)),
                ('icao', models.CharField(default='', max_length=4)),
                ('latitude', models.FloatField(blank=True, default=0, null=True)),
                ('longitude', models.FloatField(blank=True, default=0, null=True)),
                ('altitude', models.IntegerField(blank=True, default=0, null=True)),
                ('timezone_offset', models.FloatField(blank=True, default=0, null=True)),
                ('dst', models.CharField(default='', max_length=30)),
            ],
        ),
    ]