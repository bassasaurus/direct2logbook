# Generated by Django 3.1.1 on 2021-05-16 10:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0049_auto_20200904_2118'),
    ]

    operations = [
        migrations.AddField(
            model_name='flight',
            name='app_airport_detail',
            field=models.JSONField(default=str),
        ),
        migrations.AddField(
            model_name='flight',
            name='app_route_detail',
            field=models.JSONField(default=str),
        ),
    ]
