# Generated by Django 2.2.4 on 2019-11-08 19:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0034_auto_20191017_1548'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aircraft',
            name='aircraft_category',
            field=models.CharField(choices=[('', 'None'), ('A', 'Airplane'), ('R', 'Rotorcraft')], default='', max_length=30, verbose_name='Aircraft Category'),
        ),
        migrations.AlterField(
            model_name='aircraft',
            name='aircraft_class',
            field=models.CharField(choices=[('', 'None'), ('SEL', 'Single-Engine Land'), ('MEL', 'Multi-Engine Land'), ('SES', 'Single-Engine Sea'), ('MES', 'Mult-Engine Sea'), ('HELO', 'Helicopter'), ('GYRO', 'Gyroplane')], default='', max_length=30, verbose_name='Aircraft Class'),
        ),
        migrations.AlterField(
            model_name='approach',
            name='approach_type',
            field=models.CharField(choices=[('blank', ''), ('ILS', 'ILS'), ('CATII', 'CAT II'), ('CATIII', 'CAT III'), ('GPS', 'GPS'), ('RNAV', 'RNAV'), ('LOC', 'LOC'), ('VOR', 'VOR'), ('NDB', 'NDB'), ('LOC BC', 'LOC BC'), ('SDF', 'SDF'), ('LDA', 'LDA'), ('TACAN', 'TACAN'), ('MLS', 'MLS')], max_length=15, verbose_name='Approach Type'),
        ),
    ]
