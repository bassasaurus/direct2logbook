# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-06 23:20
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0031_auto_20170506_2129'),
    ]

    operations = [
        migrations.AlterField(
            model_name='total',
            name='duration',
            field=models.FloatField(unique=True),
        ),
    ]
