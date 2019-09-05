# Generated by Django 2.2.4 on 2019-08-27 22:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0018_remove_profile_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='trial_expiring',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='profile',
            name='active',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='profile',
            name='trial',
            field=models.BooleanField(default=False),
        ),
    ]
