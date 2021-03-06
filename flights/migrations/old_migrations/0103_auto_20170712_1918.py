# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-07-12 19:18
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0102_mapdata'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='mapdata',
            options={'ordering': ['airport_id'], 'verbose_name_plural': 'Map Data'},
        ),
        migrations.AddField(
            model_name='endorsement',
            name='total',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
    ]
