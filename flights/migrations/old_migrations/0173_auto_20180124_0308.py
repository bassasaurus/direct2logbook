# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-01-24 03:08
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0172_auto_20180119_2039'),
    ]

    operations = [
        migrations.AlterField(
            model_name='flight',
            name='remarks',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
