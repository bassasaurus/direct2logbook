# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-16 17:08
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0017_auto_20170216_1659'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Registration',
            new_name='TailNumber',
        ),
    ]
