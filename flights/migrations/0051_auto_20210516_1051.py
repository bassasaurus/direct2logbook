# Generated by Django 3.1.1 on 2021-05-16 10:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0050_auto_20210516_1048'),
    ]

    operations = [
        migrations.AlterField(
            model_name='flight',
            name='app_airport_detail',
            field=models.JSONField(default=dict),
        ),
    ]
