# Generated by Django 2.2.4 on 2019-10-17 15:48

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0033_auto_20191017_1547'),
    ]

    operations = [
        migrations.RenameField(
            model_name='aircraft',
            old_name='airccraft_category',
            new_name='aircraft_category',
        ),
    ]