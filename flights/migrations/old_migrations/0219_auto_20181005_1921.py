# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-10-05 19:21
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0218_auto_20181005_1919'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='approach',
            name='holding',
        ),
        migrations.AlterField(
            model_name='approach',
            name='approach_type',
            field=models.CharField(choices=[('ILS', 'ILS'), ('CATII', 'ILS CAT II'), ('CATIII', 'ILS CAT III'), ('GPS', 'GPS'), ('RNAV', 'RNAV'), ('LOC', 'LOC'), ('VOR', 'VOR'), ('NDB', 'NDB'), ('BC', 'LOC BC'), ('SDF', 'SDF'), ('LDA', 'LDA'), ('TACAN', 'TACAN'), ('MLS', 'MLS'), ('Holding', 'Holding')], max_length=15, verbose_name='Approach Type'),
        ),
    ]
