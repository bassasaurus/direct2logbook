# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-11 17:16
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0047_auto_20170511_1715'),
    ]

    operations = [
        migrations.AlterField(
            model_name='total',
            name='cross_country',
            field=models.FloatField(null=True),
        ),
    ]
