# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-06-25 23:01
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0093_regs'),
    ]

    operations = [
        migrations.RenameField(
            model_name='power',
            old_name='seat',
            new_name='role',
        ),
    ]
