# Generated by Django 2.2.4 on 2019-11-25 20:21

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0040_auto_20191125_2020'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='aircraft',
            name='category_error',
        ),
        migrations.RemoveField(
            model_name='aircraft',
            name='class_error',
        ),
        migrations.RemoveField(
            model_name='aircraft',
            name='config_error',
        ),
        migrations.RemoveField(
            model_name='aircraft',
            name='power_error',
        ),
        migrations.RemoveField(
            model_name='aircraft',
            name='weight_error',
        ),
    ]