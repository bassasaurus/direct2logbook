# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-07-15 17:38
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0111_auto_20170715_0044'),
    ]

    operations = [
        migrations.AddField(
            model_name='aircraft',
            name='image',
            field=models.FileField(blank=True, default=None, null=True, upload_to='media/aircraft/'),
        ),
    ]
