# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-11 17:08
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0045_auto_20170511_1702'),
    ]

    operations = [
        migrations.AlterField(
            model_name='total',
            name='pilot_in_command',
            field=models.FloatField(null=True),
        ),
        migrations.AlterField(
            model_name='total',
            name='second_in_command',
            field=models.FloatField(null=True),
        ),
    ]