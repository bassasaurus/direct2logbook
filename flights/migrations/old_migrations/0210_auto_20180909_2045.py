# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-09-09 20:45
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0209_auto_20180909_2044'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stat',
            name='cross_country',
            field=models.FloatField(blank=True, default=0, null=True, verbose_name='XC'),
        ),
        migrations.AlterField(
            model_name='stat',
            name='dual',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='stat',
            name='instructor',
            field=models.FloatField(blank=True, default=0, null=True, verbose_name='CFI'),
        ),
        migrations.AlterField(
            model_name='stat',
            name='instrument',
            field=models.FloatField(blank=True, default=0, null=True, verbose_name='Inst'),
        ),
        migrations.AlterField(
            model_name='stat',
            name='last_180',
            field=models.FloatField(blank=True, null=True, verbose_name='6mo'),
        ),
        migrations.AlterField(
            model_name='stat',
            name='last_2yr',
            field=models.FloatField(blank=True, null=True, verbose_name='24'),
        ),
        migrations.AlterField(
            model_name='stat',
            name='last_30',
            field=models.FloatField(blank=True, null=True, verbose_name='30'),
        ),
        migrations.AlterField(
            model_name='stat',
            name='last_60',
            field=models.FloatField(blank=True, null=True, verbose_name='60'),
        ),
        migrations.AlterField(
            model_name='stat',
            name='last_90',
            field=models.FloatField(blank=True, null=True, verbose_name='90'),
        ),
        migrations.AlterField(
            model_name='stat',
            name='last_yr',
            field=models.FloatField(blank=True, null=True, verbose_name='12mo'),
        ),
        migrations.AlterField(
            model_name='stat',
            name='night',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='stat',
            name='pilot_in_command',
            field=models.FloatField(blank=True, default=0, null=True, verbose_name='PIC'),
        ),
        migrations.AlterField(
            model_name='stat',
            name='second_in_command',
            field=models.FloatField(blank=True, default=0, null=True, verbose_name='SIC'),
        ),
        migrations.AlterField(
            model_name='stat',
            name='simulated_instrument',
            field=models.FloatField(blank=True, default=0, null=True, verbose_name='Sim Inst'),
        ),
        migrations.AlterField(
            model_name='stat',
            name='simulator',
            field=models.FloatField(blank=True, default=0, null=True, verbose_name='Sim'),
        ),
        migrations.AlterField(
            model_name='stat',
            name='solo',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='stat',
            name='total_time',
            field=models.FloatField(blank=True, default=0, verbose_name='Time'),
        ),
        migrations.AlterField(
            model_name='stat',
            name='ytd',
            field=models.FloatField(blank=True, null=True, verbose_name='YDT'),
        ),
    ]
