# Generated by Django 2.2.4 on 2019-08-20 16:37

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0018_auto_20190819_2230'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='flight',
            options={'ordering': ['pk', 'user', 'date']},
        ),
    ]
