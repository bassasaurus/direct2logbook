# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2019-04-01 19:52
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0229_auto_20190401_1946'),
    ]

    operations = [
        migrations.AlterField(
            model_name='flight',
            name='registration_error',
            field=models.CharField(blank=True, default=None, max_length=100, null=True),
        ),
    ]
