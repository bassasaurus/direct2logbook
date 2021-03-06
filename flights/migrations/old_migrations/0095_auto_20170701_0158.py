# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-07-01 01:58
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0094_auto_20170625_2301'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='aircraft',
            options={'ordering': ['aircraft_type'], 'verbose_name_plural': 'Aircraft'},
        ),
        migrations.AlterModelOptions(
            name='aircraftcategory',
            options={'verbose_name_plural': 'Aircraft Categories'},
        ),
        migrations.AlterModelOptions(
            name='aircraftclass',
            options={'verbose_name_plural': 'Aircraft Classes'},
        ),
        migrations.AlterModelOptions(
            name='approach',
            options={'ordering': ['approach_type'], 'verbose_name_plural': 'Approaches'},
        ),
        migrations.AlterModelOptions(
            name='power',
            options={'verbose_name_plural': 'Power'},
        ),
        migrations.AlterModelOptions(
            name='regs',
            options={'verbose_name_plural': 'Regs'},
        ),
        migrations.AlterModelOptions(
            name='tailnumber',
            options={'ordering': ['aircraft', 'registration'], 'verbose_name_plural': 'Tailnumbers'},
        ),
        migrations.AlterField(
            model_name='aircraft',
            name='compleks',
            field=models.NullBooleanField(verbose_name='Complex'),
        ),
        migrations.AlterField(
            model_name='flight',
            name='approaches',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='flights.Approach', verbose_name='Appr'),
        ),
        migrations.AlterField(
            model_name='flight',
            name='cross_country',
            field=models.NullBooleanField(verbose_name='XCountry'),
        ),
        migrations.AlterField(
            model_name='flight',
            name='instructor',
            field=models.NullBooleanField(verbose_name='CFI'),
        ),
        migrations.AlterField(
            model_name='flight',
            name='instrument',
            field=models.FloatField(blank=True, null=True, verbose_name='Inst'),
        ),
        migrations.AlterField(
            model_name='flight',
            name='landings_day',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Day Ldg'),
        ),
        migrations.AlterField(
            model_name='flight',
            name='landings_night',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Night Ldg'),
        ),
        migrations.AlterField(
            model_name='flight',
            name='pilot_in_command',
            field=models.NullBooleanField(verbose_name='PIC'),
        ),
        migrations.AlterField(
            model_name='flight',
            name='second_in_command',
            field=models.NullBooleanField(verbose_name='SIC'),
        ),
        migrations.AlterField(
            model_name='flight',
            name='simulated_instrument',
            field=models.FloatField(blank=True, null=True, verbose_name='Sim Inst'),
        ),
        migrations.AlterField(
            model_name='flight',
            name='simulator',
            field=models.NullBooleanField(verbose_name='Sim'),
        ),
    ]
