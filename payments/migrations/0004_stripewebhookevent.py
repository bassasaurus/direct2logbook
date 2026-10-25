from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('payments', '0003_billingprovisioning_processing_started_at_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='StripeWebhookEvent',
            fields=[
                ('event_id', models.CharField(max_length=255, primary_key=True, serialize=False)),
                ('event_type', models.CharField(max_length=255)),
                ('outcome', models.CharField(default='processed', max_length=40)),
                ('processed_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
