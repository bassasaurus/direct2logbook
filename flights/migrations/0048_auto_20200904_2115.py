# Generated by Django 3.1.1 on 2020-09-04 21:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0047_auto_20200904_2111'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tailnumber',
            name='is_121',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='tailnumber',
            name='is_135',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='tailnumber',
            name='is_91',
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
