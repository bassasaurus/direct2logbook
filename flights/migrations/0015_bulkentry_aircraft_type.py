# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2019-07-27 19:59
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0014_auto_20190727_1957'),
    ]

    operations = [
        migrations.AddField(
            model_name='bulkentry',
            name='aircraft_type',
            field=models.CharField(default=None, max_length=10),
        ),
    ]