# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-01-26 21:05
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0010_group_user'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Group',
        ),
        migrations.DeleteModel(
            name='User',
        ),
    ]
