# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-07-11 01:33
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0100_auto_20170711_0131'),
    ]

    operations = [
        migrations.AlterField(
            model_name='regs',
            name='reg_type',
            field=models.CharField(default='', max_length=5, verbose_name='Reg'),
        ),
    ]
