from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('profile', '0020_ipc_currency_reminders')]
    operations = [migrations.AddField(model_name='profile', name='web_reminder_preferences',
                                     field=models.JSONField(default=dict, blank=True, editable=False))]
