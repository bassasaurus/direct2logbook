# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-12-25 00:26
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0224_auto_20181215_2218'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tailnumber',
            name='registration',
            field=models.CharField(db_index=True, max_length=10, unique=True),
        ),
    ]