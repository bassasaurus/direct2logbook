# Generated by Django 2.2.4 on 2019-11-25 20:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0039_auto_20191125_2020'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aircraft',
            name='heavy',
            field=models.BooleanField(default=False, verbose_name='Heavy >300k lbs'),
        ),
        migrations.AlterField(
            model_name='aircraft',
            name='large',
            field=models.BooleanField(default=False, verbose_name='Large 41k-300k lbs'),
        ),
        migrations.AlterField(
            model_name='aircraft',
            name='light_sport',
            field=models.BooleanField(default=False, verbose_name='LSA <1320 lbs'),
        ),
        migrations.AlterField(
            model_name='aircraft',
            name='medium',
            field=models.BooleanField(default=False, verbose_name='Meduim 12.5-41k lbs'),
        ),
        migrations.AlterField(
            model_name='aircraft',
            name='small',
            field=models.BooleanField(default=False, verbose_name='Small <12.5k lbs'),
        ),
        migrations.AlterField(
            model_name='aircraft',
            name='superr',
            field=models.BooleanField(default=False, verbose_name='Super'),
        ),
    ]
