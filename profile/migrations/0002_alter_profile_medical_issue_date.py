from django.db import migrations, models
import datetime


def set_default_medical_issue_date(apps, schema_editor):
    Profile = apps.get_model('profile', 'Profile')
    for profile in Profile.objects.filter(medical_issue_date__isnull=True):
        profile.medical_issue_date = datetime.date.today()
        profile.save()


class Migration(migrations.Migration):

    dependencies = [
        ('profile', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(set_default_medical_issue_date),
        migrations.AlterField(
            model_name='profile',
            name='medical_issue_date',
            field=models.DateField(default=datetime.date.today),
        ),
    ]
