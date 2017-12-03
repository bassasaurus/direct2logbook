# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-08-11 17:47
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0129_auto_20170811_1739'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='mapdata',
            options={'ordering': ['country'], 'verbose_name_plural': 'Map Data'},
        ),
        migrations.RemoveField(
            model_name='mapdata',
            name='airport_id',
        ),
        migrations.AddField(
            model_name='mapdata',
            name='id',
            field=models.AutoField(auto_created=True, default=int, primary_key=True, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
    ]
