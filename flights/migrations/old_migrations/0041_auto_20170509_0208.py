# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-09 02:08
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0040_auto_20170508_0022'),
    ]

    operations = [
        migrations.AlterField(
            model_name='total',
            name='aircraft_type',
            field=models.CharField(max_length=10, unique=True),
        ),
    ]
