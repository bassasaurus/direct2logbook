# Generated by Django 2.2.4 on 2019-11-12 16:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0036_auto_20191108_1913'),
    ]

    operations = [
        migrations.AlterField(
            model_name='approach',
            name='approach_type',
            field=models.CharField(choices=[('', ''), ('ILS', 'ILS'), ('CATII', 'CAT II'), ('CATIII', 'CAT III'), ('GPS', 'GPS'), ('RNAV', 'RNAV'), ('LOC', 'LOC'), ('VOR', 'VOR'), ('NDB', 'NDB'), ('LOC BC', 'LOC BC'), ('SDF', 'SDF'), ('LDA', 'LDA'), ('TACAN', 'TACAN'), ('MLS', 'MLS')], max_length=15, verbose_name='Approach Type'),
        ),
    ]
