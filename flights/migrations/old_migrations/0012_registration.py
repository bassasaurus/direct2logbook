# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-01-30 18:06
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0011_auto_20170126_2105'),
    ]

    operations = [
        migrations.CreateModel(
            name='Registration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('registration', models.CharField(max_length=10)),
                ('is_121', models.NullBooleanField()),
                ('is_135', models.NullBooleanField()),
                ('is_91', models.NullBooleanField()),
            ],
        ),
    ]