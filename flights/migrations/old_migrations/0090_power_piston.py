# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-06-25 18:43
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0089_auto_20170625_1840'),
    ]

    operations = [
        migrations.AddField(
            model_name='power',
            name='piston',
            field=models.PositiveIntegerField(blank=True, default=0, null=True),
        ),
    ]
