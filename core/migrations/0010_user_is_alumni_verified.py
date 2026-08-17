# Migration: add is_alumni_verified field and back-fill existing alumni.
# - Adds BooleanField is_alumni_verified with default=False.
# - Auto-verifies users who already had member_type='alumni' or is_alumni=True
#   so that legacy data remains visible in the alumni directory.

from django.db import migrations, models


def backfill_verified_alumni(apps, schema_editor):
    User = apps.get_model('core', 'User')
    User.objects.filter(member_type='alumni').update(is_alumni_verified=True)
    User.objects.filter(is_alumni=True, member_type='alumni').update(is_alumni_verified=True)


def reverse_backfill(apps, schema_editor):
    # No-op: dropping the field is enough for reverse migration.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_user_graduation_year_user_is_alumni_user_member_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_alumni_verified',
            field=models.BooleanField(
                default=False,
                help_text='Admin-verified alumni status (visible in alumni directory)',
            ),
        ),
        migrations.RunPython(backfill_verified_alumni, reverse_backfill),
    ]
