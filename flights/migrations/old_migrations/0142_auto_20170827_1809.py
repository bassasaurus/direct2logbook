# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-08-27 18:09
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0141_auto_20170827_1802'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tailnumber',
            name='registration',
            field=models.CharField(db_index=True, max_length=10),
        ),
    ]
