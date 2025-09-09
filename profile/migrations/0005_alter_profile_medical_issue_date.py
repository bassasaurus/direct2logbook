import django.utils.timezone
from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('profile', '0004_alter_profile_medical_issue_date'),
    ]

    operations = [
        migrations.RunSQL(
            sql="UPDATE profile_profile SET medical_issue_date = CURRENT_DATE WHERE medical_issue_date IS NULL;",
            reverse_sql="UPDATE profile_profile SET medical_issue_date = NULL WHERE medical_issue_date = CURRENT_DATE;",
        ),
        migrations.AlterField(
            model_name='profile',
            name='medical_issue_date',
            field=models.DateField(
                null=False, blank=False, default=datetime.date.today),
        ),
    ]
