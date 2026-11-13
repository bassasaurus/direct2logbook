from django.db import migrations


def ensure_cleanup_table(apps, schema_editor):
    # Legacy installations recorded an older accounts.0001_initial before the
    # migration files were removed. Their history collides with the new initial
    # migration, so state says this model exists even though its table does not.
    model = apps.get_model('accounts', 'AccountDeletionCleanup')
    if model._meta.db_table not in schema_editor.connection.introspection.table_names():
        schema_editor.create_model(model)


class Migration(migrations.Migration):
    dependencies = [('accounts', '0001_initial')]
    operations = [migrations.RunPython(ensure_cleanup_table, migrations.RunPython.noop)]
