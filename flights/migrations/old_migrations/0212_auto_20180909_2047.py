# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-09-09 20:47
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0211_auto_20180909_2046'),
    ]

    operations = [
        migrations.AlterField(
            model_name='endorsement',
            name='total',
            field=models.DecimalField(blank=True, db_index=True, decimal_places=1, default=0, max_digits=6, null=True),
        ),
        migrations.AlterField(
            model_name='power',
            name='piston',
            field=models.DecimalField(blank=True, decimal_places=1, default=0, max_digits=6, null=True),
        ),
        migrations.AlterField(
            model_name='power',
            name='turbine',
            field=models.DecimalField(blank=True, decimal_places=1, default=0, max_digits=6, null=True),
        ),
        migrations.AlterField(
            model_name='regs',
            name='pilot_in_command',
            field=models.DecimalField(blank=True, decimal_places=1, default=0, max_digits=6, null=True, verbose_name='PIC'),
        ),
        migrations.AlterField(
            model_name='regs',
            name='second_in_command',
            field=models.DecimalField(blank=True, decimal_places=1, default=0, max_digits=6, null=True, verbose_name='SIC'),
        ),
        migrations.AlterField(
            model_name='weight',
            name='total',
            field=models.DecimalField(blank=True, decimal_places=1, default=0, max_digits=6, null=True),
        ),
    ]
