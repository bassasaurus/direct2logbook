# Generated by Django 2.2.4 on 2019-08-31 22:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0021_auto_20190828_1457'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='admin',
            field=models.BooleanField(default=False),
        ),
    ]
