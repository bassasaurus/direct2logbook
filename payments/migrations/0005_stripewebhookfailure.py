from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('payments', '0004_stripewebhookevent')]

    operations = [
        migrations.CreateModel(
            name='StripeWebhookFailure',
            fields=[
                ('event_id', models.CharField(max_length=255, primary_key=True, serialize=False)),
                ('event_type', models.CharField(max_length=255)),
                ('attempts', models.PositiveIntegerField(default=0)),
                ('first_failed_at', models.DateTimeField(auto_now_add=True)),
                ('last_failed_at', models.DateTimeField()),
                ('last_alerted_at', models.DateTimeField(blank=True, null=True)),
            ],
        ),
    ]
